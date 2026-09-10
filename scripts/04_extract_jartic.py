"""4. JARTIC 交通規制情報から、市域に掛かる速度・中央線・通行帯の規制を切り出す。

入力は jartic-traffic-regulation-converter の parse_regulation.py が出す GeoJSONL
(regulation_speed.geojsonl / regulation_lane.geojsonl)。都道府県コードで絞らず
空間で絞る(JARTIC の都道府県コードは JIS と異なる。埼玉=12 など)。

    uv run python scripts/04_extract_jartic.py --area kawagoe --jartic data/jartic/202607
"""
import json

import geopandas as gpd
import pandas as pd

import common

# 共通規制種別コード → 用途
KIND = {
    "61": "speed", "112": "speed", "113": "speed", "114": "speed",  # 最高速度(線・面・高速)
    "15": "centerline",                                           # 道路の中央線
    "16": "lane", "17": "lane", "20": "lane", "21": "lane", "118": "lane",  # 通行帯系
}

p = common.parser(__doc__)
p.add_argument("--jartic", default="data/jartic/202607", help="regulation_*.geojsonl があるディレクトリ")
args = p.parse_args()
area = common.Area(args.area)
city = area.geometry()
src = common.ROOT / args.jartic

feats = []
for layer in ("speed", "lane"):
    with open(src / f"regulation_{layer}.geojsonl", encoding="utf-8") as f:
        feats.extend(json.loads(line) for line in f)
g = gpd.GeoDataFrame.from_features(feats, crs=4326)
g = g[g.intersects(city)].copy()
g["kind"] = g["code"].map(KIND)
g = g[g.kind.notna()]
g["jartic_month"] = src.name

pd.set_option("display.width", 200)
print(f"{area.name}: JARTIC {src.name}")
print(g.groupby(["code", "kind_name" if "kind_name" in g else "kind", "shape_name"]).size().to_string())

lines = g[g.geom_type.isin(["LineString", "MultiLineString"])]
polys = g[g.geom_type.isin(["Polygon", "MultiPolygon"])]
lm = lines.to_crs(area.epsg)
print("\n速度規制(線) 速度別 km:", (lm[lm.kind == "speed"].groupby("speed").geometry.apply(lambda s: s.length.sum() / 1000)).round(1).to_dict())
print("中央線 km:", round(lm[lm.kind == "centerline"].length.sum() / 1000, 1), "/ 通行帯 km:", round(lm[lm.kind == "lane"].length.sum() / 1000, 1))
pm = polys.to_crs(area.epsg)
if len(pm):
    print("速度規制(面):\n", pm[pm.kind == "speed"].groupby(["speed", "zone30"], dropna=False).geometry.agg(n="size", km2=lambda s: round(s.area.sum() / 1e6, 2)).to_string())

lines.to_file(area.jartic_lines, driver="GeoJSON")
polys.to_file(area.jartic_polygons, driver="GeoJSON")
