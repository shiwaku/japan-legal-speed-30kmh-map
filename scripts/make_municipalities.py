"""市区町村別の集計とビューワ用の境界データを作る。

- 都道府県ごとの判定結果 out/pref_<code>/final.parquet を読み、各線分の中点が入る
  市区町村(国土数値情報 N03-20240101)に割り当てて final / speed_before / speed_after 別の延長を集計する
  (中点方式なので市区町村境をまたぐ線分は片方に丸ごと入る。03 の都道府県割り当てと同じ)
- 政令指定都市は区ごとに加えて市全体(コード XX100)も出す
- 出力
  - viewer/public/municipalities.json: {code: {name, pref_name, lv, bbox, car_km, changed_km, pct, total_km,
    classes, speed_before, speed_after}}。lv 0=市区町村, 1=政令市の区, 2=政令市全体(区と重なるので面塗り・境界線から外す)
  - data/n03/municipalities.fgb / municipalities_points.fgb: 境界と代表点(変更率つき)。
    06_build_municipalities_pmtiles.sh で 2 レイヤーの PMTiles にする(面塗りとラベル用)
道路統計年報は都道府県単位なので、市区町村では道路法換算(下限〜上限)は出さない。
"""
from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

N03_ZIP = common.DATA / "n03" / "N03-20240101_GML.zip"
OUT_JSON = common.DOCS / "municipalities.json"
OUT_FGB = common.DATA / "n03" / "municipalities.fgb"
OUT_PTS = common.DATA / "n03" / "municipalities_points.fgb"

with zipfile.ZipFile(N03_ZIP) as z:
    shp = next(n for n in z.namelist() if n.endswith(".shp"))
n03 = gpd.read_file(f"zip://{N03_ZIP}!{shp}", encoding="utf-8").to_crs(4326)
n03 = n03[n03["N03_007"].notna()].copy()
# 「所属未定地」はコードが都道府県+000(千葉 12000・東京 13000 の中央防波堤埋立地・沖縄 47000)。
# 市区町村ではないので集計・面塗り・順位から外す
n03 = n03[~n03["N03_007"].astype(str).str.zfill(5).str.endswith("000")].copy()
n03["code"] = n03["N03_007"].astype(str).str.zfill(5)
n03["pref_code"] = n03["code"].str[:2]
n03["pref_name"] = n03["N03_001"]
n03["city"] = n03["N03_004"].fillna("")
n03["ward"] = n03["N03_005"].fillna("")
n03["name"] = n03["city"] + n03["ward"]
print(f"N03: {len(n03)} polygons, {n03['code'].nunique()} codes")
# 市区町村数の内訳(政令市は 1 市として数える)。総務省の市区町村数 1,741 +
# 北方領土 6 村(N03 に含まれる)= 1,747 になるはず
_kinds = n03.drop_duplicates("code")["name"].str[-1].value_counts().to_dict()
print(f"  内訳(末尾の字): {_kinds}")

# 境界(コードで結合)。政令市の市全体も 1 つの地物にする
muni = n03.dissolve(by="code", aggfunc={"name": "first", "pref_code": "first", "pref_name": "first", "city": "first", "ward": "first"}).reset_index()
desig = muni[muni["ward"] != ""].dissolve(by="city", aggfunc={"pref_code": "first", "pref_name": "first"}).reset_index()
# 政令市のコードは N03 に無い。区コードは市コードの直後から連番(横浜 14100→14101…, 川崎 14130→14131…)なので
# 最小の区コードを 10 の位で切り下げる
city_code = {c: f"{int(g['code'].min()) // 10 * 10:05d}" for c, g in muni[muni["ward"] != ""].groupby("city")}
desig["code"] = desig["city"].map(city_code)
desig["name"] = desig["city"]
desig["ward"] = ""
muni = pd.concat([muni, desig[muni.columns]], ignore_index=True)
muni = gpd.GeoDataFrame(muni, geometry="geometry", crs=4326).sort_values("code").reset_index(drop=True)
muni["lv"] = 0
muni.loc[muni["ward"] != "", "lv"] = 1
muni.loc[muni["code"].isin(city_code.values()), "lv"] = 2
print(f"municipalities: {len(muni)} (区 {int((muni['lv'] == 1).sum())}, 政令市全体 {int((muni['lv'] == 2).sum())})")

bounds = muni.bounds
info: dict[str, dict] = {}
for r, b in zip(muni.itertuples(), bounds.itertuples()):
    info[r.code] = {
        "name": r.name, "pref_code": r.pref_code, "pref_name": r.pref_name, "city": r.city, "ward": r.ward, "lv": r.lv,
        "bbox": [round(b.minx, 4), round(b.miny, 4), round(b.maxx, 4), round(b.maxy, 4)],
    }

def tally(df: pd.DataFrame, col: str) -> dict[str, float]:
    s = df.groupby(col)["len_m"].sum() / 1000
    return {k: round(float(v), 1) for k, v in s.sort_values(ascending=False).items() if v > 0}

for code in sorted(n03["pref_code"].unique()):
    src = common.ROOT / "out" / f"pref_{code}" / "final.parquet"
    if not src.exists():
        print(code, "final.parquet が無い"); continue
    roads = gpd.read_parquet(src)
    polys = muni[(muni["pref_code"] == code) & ~muni["code"].isin(city_code.values())]  # 区 + 区を持たない市町村(市全体は除く)
    polys = polys.to_crs(roads.crs)[["code", "geometry"]]
    pts = gpd.GeoDataFrame(roads[["len_m", "final", "speed_before", "speed_after"]], geometry=roads.geometry.interpolate(0.5, normalized=True), crs=roads.crs)
    j = gpd.sjoin(pts, polys, how="left", predicate="within")
    j = j[~j.index.duplicated(keep="first")]
    miss = j["code"].isna()
    if miss.any():  # 海岸線のずれなどで外に出た中点は最寄りに
        near = gpd.sjoin_nearest(pts[miss], polys, how="left", max_distance=2000)
        near = near[~near.index.duplicated(keep="first")]
        j.loc[miss, "code"] = near["code"]
    j = j[j["code"].notna()]
    print(f"{code}: {len(roads)} segments, {int(miss.sum())} outside → nearest, {int((~j.index.isin(roads.index)).sum())} dropped")
    for mcode, g in j.groupby("code"):
        info[mcode].update({"total_km": round(float(g["len_m"].sum()) / 1000, 1), "classes": tally(g, "final"),
                            "speed_before": tally(g, "speed_before"), "speed_after": tally(g, "speed_after")})
    # 政令市の市全体
    for city, g in j[j["code"].isin(muni.loc[muni["ward"] != "", "code"])].merge(muni[["code", "city"]], on="code").groupby("city"):
        ccode = city_code[city]
        info[ccode].update({"total_km": round(float(g["len_m"].sum()) / 1000, 1), "classes": tally(g, "final"),
                            "speed_before": tally(g, "speed_before"), "speed_after": tally(g, "speed_after")})

info = {k: v for k, v in info.items() if "total_km" in v}

# 車道(中心線から軽車道・徒歩道等を除いたもの)と変更率。面塗り・ランキングに使う。
# 区分名は言い換えられることがあるので "(ftCode)" で終わるものを非車道として引く
for v in info.values():
    non_road = sum(km for cls, km in v["classes"].items() if cls.endswith("(ftCode)"))
    car = v["total_km"] - non_road
    changed = v["classes"].get(common.FINAL_CHANGED, 0.0)
    v["car_km"] = round(car, 1)
    v["changed_km"] = round(changed, 1)
    v["pct"] = round(changed / car * 100, 1) if car > 0 else None

OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
OUT_JSON.write_text(json.dumps(info, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
# タイル用(面 + 代表点)。ビューワは pct で面を塗り、代表点に変更率のラベルを出す
stat = pd.DataFrame([{"code": c, "car_km": v["car_km"], "changed_km": v["changed_km"], "pct": v["pct"]} for c, v in info.items()])
g = muni.merge(stat, on="code")
cols = ["code", "name", "pref_code", "pref_name", "lv", "car_km", "changed_km", "pct", "geometry"]
g[cols].to_file(OUT_FGB, driver="FlatGeobuf")
pts = g.copy()
pts["geometry"] = g.representative_point()  # 面の内側の点(ラベル位置)
pts[cols].to_file(OUT_PTS, driver="FlatGeobuf")

pcts = pd.Series([v["pct"] for v in info.values() if v["lv"] != 2 and v["pct"] is not None])
print(f"wrote {OUT_JSON} ({OUT_JSON.stat().st_size / 1e6:.1f} MB, {len(info)} entries), {OUT_FGB}, {OUT_PTS}")
print(f"変更率(政令市全体を除く {len(pcts)} 件): 中央値 {pcts.median():.1f}% / 最小 {pcts.min():.1f}% / 最大 {pcts.max():.1f}%")
print(pcts.describe(percentiles=[0.1, 0.25, 0.5, 0.75, 0.9]).round(1).to_string())
