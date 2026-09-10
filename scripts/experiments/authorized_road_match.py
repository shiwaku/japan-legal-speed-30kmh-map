"""実験: 自治体の認定路線網図(道路法の認定路線)で、地理院中心線を線分単位に「道路法上の道路か」判定する。

areas/<key>.json の authorized_road に従い data/areas/<key>/authorized_road/*.shp を読み、
GSI 線分ごとに 10 m バッファで認定路線との重なり率を出す。重なり ≥0.5 を認定路線とみなす。
認定路線でない線分 ＝ 私道・農道・未認定道路・国道/道道(市の網図に無い)など。
道路統計との差(市区町村道の超過)と、認定路線外の km がどれだけ合うかを見る。

    uv run python scripts/experiments/authorized_road_match.py sapporo
"""
import glob
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
import shapely

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import common

area = common.Area(sys.argv[1] if len(sys.argv) > 1 else "sapporo")
cfg = area.cfg.get("authorized_road")
if not cfg:
    raise SystemExit(f"areas/{area.key}.json に authorized_road が無い")
shp = glob.glob(str(area.data / "authorized_road" / "**" / "*.shp"), recursive=True)
if not shp:
    raise SystemExit(f"{area.data / 'authorized_road'} に shapefile が無い。{cfg.get('source')} から取る")

auth = gpd.read_file(shp[0], encoding="cp932")
auth = (auth.set_crs(cfg["epsg"], allow_override=True) if auth.crs is None else auth).to_crs(area.epsg)
auth["km"] = auth.length / 1000
pd.set_option("display.width", 200)
print(f"認定路線網図: {len(auth)} 本 {auth.km.sum():.0f} km  ({cfg.get('as_of')})")
if "路線区分" in auth:
    print(auth.groupby("路線区分").km.sum().round(1).to_string())

roads = gpd.read_parquet(area.out / "final.parquet")
roads = roads[roads.ftCode.between(2701, 2704)].reset_index(drop=True)
roads["seg_id"] = roads.index
buf = auth[["geometry"] + [c for c in ("路線区分", "幅員最小", "幅員最大") if c in auth]].copy()
buf["geometry"] = buf.geometry.buffer(10, cap_style="flat")
j = gpd.sjoin(roads[["seg_id", "len_m", "geometry"]], buf, how="inner", predicate="intersects")
inter = shapely.intersection(j.geometry.values, buf.geometry.values[j.index_right.values])
j["ol"] = shapely.length(inter)
j = j.sort_values("ol", ascending=False).drop_duplicates("seg_id")
j["frac_auth"] = (j.ol / j.len_m).clip(upper=1)
roads = roads.merge(j.drop(columns=["geometry", "len_m", "index_right", "ol"]), on="seg_id", how="left")
roads["frac_auth"] = roads.frac_auth.fillna(0)
roads["authorized"] = roads.frac_auth >= 0.5

total = roads.len_m.sum() / 1000
by = roads.groupby(["rdCtg", "authorized"]).len_m.sum().unstack(fill_value=0) / 1000
by.index = by.index.map({0: "国道", 1: "都道府県道", 2: "市区町村道", 3: "高速自動車国道等"})
print("\nGSI 通常道路 km × 認定路線に乗るか:\n", by.round(1).to_string())
off = area.cfg["official_road_km"]
gsi_muni = roads.loc[roads.rdCtg == 2, "len_m"].sum() / 1000
print(f"\n市区町村道: GSI {gsi_muni:.0f} km / 道路統計 {off['市区町村道']:.0f} km / 差 {gsi_muni - off['市区町村道']:.0f} km"
      f" ← 認定路線に乗らない市区町村道 {by.loc['市区町村道', False]:.0f} km")

fin = roads.pivot_table(index="final", columns="authorized", values="len_m", aggfunc="sum", fill_value=0) / 1000
print("\n判定クラス × 認定路線 km:\n", fin.round(1).to_string())
a = roads[roads.authorized]
b_all = roads.loc[roads.final == common.FINAL_CHANGED, "len_m"].sum() / 1000
b_auth = a.loc[a.final == common.FINAL_CHANGED, "len_m"].sum() / 1000
c_auth = a.loc[a.cls == common.CLS_CANDIDATE, "len_m"].sum() / 1000
print(f"\n60→30 変更: 全体 {b_all:.0f}/{total:.0f} km = {b_all / total * 100:.1f}%  →  認定路線のみ {b_auth:.0f}/{a.len_m.sum() / 1000:.0f} km = {b_auth / a.len_m.sum() * 1e5:.1f}%")
print(f"構造的に対象(5.5m未満・分離帯なし): 認定路線のみ {c_auth / a.len_m.sum() * 1e5:.1f}%")

if "幅員最小" in roads:
    # 認定路線網図の幅員(道路台帳)と地理院 rnkWidth の突き合わせ
    w = roads[roads.authorized & roads["幅員最小"].notna()].copy()
    w["auth_w"] = pd.cut(w["幅員最小"], [0, 3, 5.5, 13, 19.5, 100], labels=["<3", "3-5.5", "5.5-13", "13-19.5", ">=19.5"], right=False)
    print("\n地理院 rnkWidth(行) × 認定路線網図 幅員最小(列) km:\n", (w.pivot_table(index="rnkWidth", columns="auth_w", values="len_m", aggfunc="sum", fill_value=0, observed=False) / 1000).round(0).to_string())

roads.drop(columns=["geometry"]).to_csv(area.out / "authorized_match.csv", index=False)
print(f"\nsaved {area.out / 'authorized_match.csv'}")
