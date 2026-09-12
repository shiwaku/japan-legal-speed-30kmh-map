"""3. タイルの road レイヤーから道路中心線(ftCode 27xx)を取り出し、一次判定する。

タイル矩形でクリップ(隣接タイルとの重複除去) → 市域でクリップ → 属性クロス集計。

    uv run python scripts/03_decode_roads.py --area kawagoe
"""
import gzip

import geopandas as gpd
import mapbox_vector_tile
import mercantile
import pandas as pd
import shapely
import shapely.ops
from shapely import affinity
from shapely.geometry import box, shape

import common

args = common.parser(__doc__).parse_args()
area = common.Area(args.area)
city = area.geometry()

recs = []
for p in sorted(area.tiles_dir.glob("*.pbf")):
    z, x, y = map(int, p.stem.split("_"))
    b = p.read_bytes()
    if b[:2] == b"\x1f\x8b":
        b = gzip.decompress(b)
    t = mapbox_vector_tile.decode(b, default_options={"y_coord_down": True})
    if "road" not in t:
        continue
    ext = t["road"]["extent"]
    tb = mercantile.xy_bounds(x, y, z)  # web mercator
    sx = (tb.right - tb.left) / ext
    sy = (tb.top - tb.bottom) / ext
    clipbox = box(0, 0, ext, ext)
    for f in t["road"]["features"]:
        pr = f["properties"]
        ft = pr.get("ftCode", 0)
        if not 2700 <= ft < 2800:  # 2201 道路縁 などは除外
            continue
        g = shape(f["geometry"]).intersection(clipbox)  # タイルバッファ部を落とす
        if g.geom_type == "GeometryCollection":
            g = shapely.ops.unary_union([q for q in g.geoms if "Line" in q.geom_type])
        if g.is_empty or "Line" not in g.geom_type:  # 矩形境界で点になったものは捨てる
            continue
        g = affinity.affine_transform(g, [sx, 0, 0, -sy, tb.left, tb.top])  # px → 3857
        recs.append(
            dict(
                z=z, x=x, y=y, ftCode=ft,
                rdCtg=pr.get("rdCtg"), rnkWidth=pr.get("rnkWidth"), medSect=pr.get("medSect"),
                motorway=pr.get("motorway"), tollSect=pr.get("tollSect"), lvOrder=pr.get("lvOrder"),
                orgGILvl=pr.get("orgGILvl"), geometry=g,
            )
        )

gdf = gpd.GeoDataFrame(recs, geometry="geometry", crs=3857).to_crs(area.epsg)
gdf["len_all_m"] = gdf.length
city_m = gpd.GeoSeries([city], crs=4326).to_crs(area.epsg).iloc[0]
gdf["in_city"] = gdf.intersects(city_m)
gdf["geom_city"] = gdf.geometry.intersection(city_m)
gdf["len_city_m"] = gdf["geom_city"].length
gdf["cls"] = [
    common.classify_width(r.ftCode, r.rdCtg, r.rnkWidth, r.medSect, r.motorway)
    for r in gdf.itertuples()
]

# ---- 出力 -------------------------------------------------------------------
gdf.drop(columns=["geom_city"]).to_parquet(area.out / "roads_z16.parquet")
gc = gdf[gdf.in_city].drop(columns=["geometry"]).rename(columns={"geom_city": "geometry"})
gc = gpd.GeoDataFrame(gc, geometry="geometry", crs=area.epsg)
gc = gc[~gc.geometry.is_empty]
# 05 は parquet を優先して読む。03' (GDAL 版) と混ぜたときに古い parquet が残らないよう、こちらも書く
gc.to_parquet(area.out / "roads_city.parquet")
gc.to_crs(4326).to_file(area.out / "roads_city.geojson", driver="GeoJSON")


def tab(df, by, col="len_city_m"):
    s = df.groupby(by, dropna=False)[col].sum() / 1000
    return pd.concat([s.rename("km"), (s / s.sum() * 100).rename("%").round(1)], axis=1)


pd.set_option("display.width", 200)
inc = gdf[gdf.in_city]
print(f"{area.name}: features {len(gdf)}, 市域内 {len(inc)}, 市域内延長 {inc.len_city_m.sum() / 1000:.1f} km\n")
print("## ftCode\n", tab(inc, "ftCode"), "\n")
cl = inc[inc.ftCode.between(2701, 2704)]
print("## 車道(軽車道・徒歩道等を除く) (ftCode 2701-2704) --------------------------------------")
for col in ("rnkWidth", "medSect", "rdCtg", "motorway", "orgGILvl"):
    print(f"## {col}\n", tab(cl, col), "\n")
print("## rnkWidth x rdCtg (km)\n", (cl.pivot_table(index="rnkWidth", columns="rdCtg", values="len_city_m", aggfunc="sum", fill_value=0) / 1000).round(1), "\n")
print("## 一次判定\n", tab(inc, "cls"), "\n")
tab(inc, "cls").to_csv(area.out / "summary_cls.csv")
tab(cl, ["rnkWidth", "medSect", "rdCtg", "motorway"]).to_csv(area.out / "summary_attrs.csv")
