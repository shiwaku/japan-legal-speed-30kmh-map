"""5. 道路中心線(市域クリップ済)と JARTIC 規制を重なり率で突合し、最終判定を出す。

規制線を --buffer m でバッファし、GSI 線分の長さのうちバッファ内にある比率 frac を
種別ごとに計算する。交差判定だと規制道路に接続する脇道が端点で全部引っかかるため。

    uv run python scripts/05_match_regulation.py --area kawagoe --buffer 10 --save
"""
import datetime as dt
import json

import geopandas as gpd
import matplotlib
import pandas as pd
import shapely

import common

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

p = common.parser(__doc__)
p.add_argument("--buffer", type=float, default=10.0, help="規制線のバッファ幅 m")
p.add_argument("--th-line", type=float, default=0.7, help="線規制と見なす重なり率")
p.add_argument("--th-poly", type=float, default=0.5, help="面規制(ゾーン30)と見なす内包率")
p.add_argument("--save", action="store_true", help="out/<area>/final.* と docs/areas.json を書く")
args = p.parse_args()
area = common.Area(args.area)

roads = gpd.read_file(area.out / "roads_city.geojson").to_crs(area.epsg)
roads = roads[roads.length > 0].reset_index(drop=True)
roads["seg_id"] = roads.index
roads["len_m"] = roads.length
jl = gpd.read_file(area.jartic_lines).to_crs(area.epsg)
jp = gpd.read_file(area.jartic_polygons).to_crs(area.epsg) if area.jartic_polygons.exists() else jl.iloc[0:0]
jp = jp[jp.kind == "speed"]
jartic_month = str(jl.jartic_month.iloc[0]) if "jartic_month" in jl and len(jl) else "?"


def overlap_frac(segs, polys, key=None):
    """segs の各線分について polys(面)との交差長 / 線分長。key があれば key ごと。"""
    cols = ["geometry"] + ([key] if key else [])
    polys = polys[cols].reset_index(drop=True)
    j = gpd.sjoin(segs[["seg_id", "geometry"]], polys, how="inner", predicate="intersects")
    if j.empty:
        return pd.DataFrame(columns=["seg_id", "frac"] + ([key] if key else []))
    inter = shapely.intersection(j.geometry.values, polys.geometry.values[j.index_right.values])
    j["ol"] = shapely.length(inter)
    o = j.groupby(["seg_id"] + ([key] if key else []))["ol"].sum().reset_index()
    o = o.merge(segs[["seg_id", "len_m"]], on="seg_id")
    o["frac"] = (o.ol / o.len_m).clip(upper=1.0)
    return o


def buffered(df):
    b = df.copy()
    b["geometry"] = b.geometry.buffer(args.buffer, cap_style="flat")
    return b


def best(o, key):
    return o.sort_values("frac", ascending=False).drop_duplicates("seg_id")[["seg_id", "frac", key]]


sp = best(overlap_frac(roads, buffered(jl[jl.kind == "speed"]), key="speed"), "speed")
roads = roads.merge(sp.rename(columns={"frac": "frac_speed", "speed": "reg_speed"}), on="seg_id", how="left")
pz = best(overlap_frac(roads, jp, key="speed"), "speed") if len(jp) else pd.DataFrame(columns=["seg_id", "frac", "speed"])
roads = roads.merge(pz.rename(columns={"frac": "frac_zone", "speed": "zone_speed"}), on="seg_id", how="left")
for kind, col in (("lane", "frac_lane"), ("centerline", "frac_cl")):
    o = overlap_frac(roads, buffered(jl[jl.kind == kind]))
    roads = roads.merge(o[["seg_id", "frac"]].rename(columns={"frac": col}), on="seg_id", how="left")
fcols = ["frac_speed", "frac_zone", "frac_lane", "frac_cl"]
roads[fcols] = roads[fcols].fillna(0.0)

roads["final"] = [
    common.classify_final(r.cls, r.frac_speed, r.reg_speed, r.frac_zone, r.zone_speed, r.frac_lane, r.frac_cl, args.th_line, args.th_poly)
    for r in roads.itertuples()
]
ba = [common.speed_before_after(r.final, r.reg_speed, r.zone_speed) for r in roads.itertuples()]
roads["speed_before"] = [b for b, _ in ba]
roads["speed_after"] = [a for _, a in ba]

# ---- 集計 -------------------------------------------------------------------
pd.set_option("display.width", 200)
s = roads.groupby("final")["len_m"].sum() / 1000
summary = pd.concat([s.rename("km").round(1), (s / s.sum() * 100).rename("%").round(1)], axis=1).sort_values("km", ascending=False)
print(f"=== {area.name}  buffer {args.buffer} m / 線 {args.th_line} / 面 {args.th_poly} / JARTIC {jartic_month}  (市域内 {s.sum():.0f} km)")
print(summary.to_string())
cand = roads[roads.cls == common.CLS_CANDIDATE]
bins = pd.cut(cand.frac_speed, [-0.01, 0, 0.3, 0.5, 0.7, 0.9, 1.0])
print("\n候補(5.5m未満)の frac_speed 分布 km:", {str(k): round(v, 1) for k, v in (cand.groupby(bins, observed=False)["len_m"].sum() / 1000).items()})

if not args.save:
    raise SystemExit

# ---- 出力 -------------------------------------------------------------------
roads.to_parquet(area.out / "final.parquet")
roads.to_crs(4326).to_file(area.out / "final.geojson", driver="GeoJSON")
summary.to_csv(area.out / "summary_final.csv")

# ビューワの目録。エリアごとに上書き
manifest_path = common.DOCS / "areas.json"
manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
manifest[area.key] = {
    "name": area.name,
    "view": area.view,
    "jartic_month": jartic_month,
    "buffer_m": args.buffer,
    "generated": dt.date.today().isoformat(),
    "total_km": round(float(s.sum()), 1),
    "classes": {k: round(float(v), 1) for k, v in s.sort_values(ascending=False).items()},
    "speed_before": {k: round(float(v), 1) for k, v in (roads.groupby("speed_before")["len_m"].sum() / 1000).items()},
    "speed_after": {k: round(float(v), 1) for k, v in (roads.groupby("speed_after")["len_m"].sum() / 1000).items()},
}
bs = roads.pivot_table(index="speed_before", columns="speed_after", values="len_m", aggfunc="sum", fill_value=0) / 1000
print("\n## 改正前(行) → 改正後(列) km\n", bs.round(1).to_string())
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

# 判定図。日本語フォントは環境にあるものを1つ選ぶ(無ければ豆腐になるだけで落ちない)
from matplotlib import font_manager  # noqa: E402

installed = {f.name for f in font_manager.fontManager.ttflist}
jp_font = next((f for f in ("Yu Gothic", "Meiryo", "Noto Sans CJK JP", "Noto Sans JP", "IPAexGothic", "Hiragino Sans") if f in installed), "sans-serif")
fig, ax = plt.subplots(figsize=(18, 14), dpi=110)
gpd.read_file(area.boundary).to_crs(area.epsg).boundary.plot(ax=ax, color="k", lw=0.8)
for k, c in common.FINAL_STYLE:
    sub = roads[roads.final == k]
    if len(sub):
        sub.plot(ax=ax, color=c, lw=0.5 if k in (common.FINAL_CHANGED, common.CLS_MINOR) else 1.3, label=f"{k}  {sub.len_m.sum() / 1000:.0f} km")
ax.legend(loc="lower left", prop={"family": jp_font, "size": 10})
ax.set_title(f"{area.name}  生活道路 30 km/h 判定  (JARTIC {jartic_month}, buffer {args.buffer:g} m)", fontfamily=jp_font)
ax.set_axis_off()
plt.savefig(area.out / "final.png", bbox_inches="tight")
print(f"saved {area.out}/final.* , {manifest_path}")
