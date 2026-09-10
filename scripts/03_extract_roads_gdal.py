"""3'. 地理院ベクトルタイルの道路中心線を GDAL で一括抽出し、一次判定する(全国版・都道府県単位用)。

01〜03(タイルを 1 枚ずつ Python で decode)と同じ結果を、WSL の GDAL MVT ドライバで数十秒〜数分で出す。
  --source experimental (既定): experimental_bvmap ZL16 タイルを z/x/y に置いたディレクトリ
                                (scripts/download_tiles_all.sh → ~/gsi/experimental_bvmap/16)。medSect あり
  --source optimal            : 最適化ベクトルタイルの全国 PMTiles (~/gsi/optimal_bvmap-v1.pmtiles)。medSect なし

市域への割り当ては --assign で選ぶ:
  clip     (既定: 市区町村): 市域ポリゴンでクリップし、市域内の長さを測る(川越・札幌と同じ)
  midpoint (既定: 都道府県): 線分の代表点が県域に入るかで割り当てる。県境で線分は切らないが、
                             128 万本のクリップに 20 分かかるのを数十秒にできる。県境をまたぐ線分の長さ誤差は無視できる

    uv run python scripts/03_extract_roads_gdal.py --area pref_11
    uv run python scripts/03_extract_roads_gdal.py --area kawagoe --assign clip
"""
import os
import subprocess
import sys

import geopandas as gpd
import pandas as pd

import common

SRC = {
    "experimental": {"path": os.environ.get("EXPERIMENTAL_TILES_WSL", "/home/shi-works/gsi/experimental_bvmap") + "/16",
                     "prefix": "MVT:", "layer": "road", "medsect": True},
    "optimal": {"path": os.environ.get("OPTIMAL_BVMAP_PMTILES", "/home/shi-works/gsi/optimal_bvmap-v1.pmtiles"),
                "prefix": "", "layer": "RdCL", "medsect": False},
}
RNKWIDTH = {"3m未満": 0, "3m-5.5m未満": 1, "5.5m-13m未満": 2, "13m-19.5m未満": 3, "19.5m以上": 4, "その他": 5, "不明": 6}
RDCTG = {"国道": 0, "都道府県道": 1, "市区町村道等": 2, "高速自動車国道等": 3, "その他": 5, "不明": 6}


def to_wsl(p):
    p = str(p).replace("\\", "/")
    return f"/mnt/{p[0].lower()}{p[2:]}" if len(p) > 1 and p[1] == ":" else p


p = common.parser(__doc__)
p.add_argument("--source", choices=SRC, default="experimental")
p.add_argument("--assign", choices=["clip", "midpoint"], default=None)
p.add_argument("--refetch", action="store_true", help="抽出済みの fgb を作り直す")
args = p.parse_args()
area = common.Area(args.area)
src = SRC[args.source]
assign = args.assign or ("midpoint" if area.cfg.get("kind") == "prefecture" else "clip")
city = area.geometry()
w, s, e, n = city.bounds

fgb_dir = common.DATA / "gsi" / args.source
fgb_dir.mkdir(parents=True, exist_ok=True)
fgb = fgb_dir / f"{area.key}.fgb"
if args.refetch or not fgb.exists():
    # MVT ドライバは EPSG:3857 で返すので -spat_srs を付ける。CLIP=YES でタイルバッファ部を落とす(隣接タイルとの重複除去)。
    # クリップで点になった線分は -skipfailures で捨てる。失敗したら作りかけの fgb を消す
    cmd = ["wsl", "ogr2ogr", "-f", "FlatGeobuf", to_wsl(fgb), src["prefix"] + src["path"], src["layer"],
           "-oo", "ZOOM_LEVEL=16", "-oo", "CLIP=YES",
           "-spat", f"{w:.5f}", f"{s:.5f}", f"{e:.5f}", f"{n:.5f}", "-spat_srs", "EPSG:4326", "-t_srs", "EPSG:4326",
           "-nlt", "MULTILINESTRING", "-skipfailures"]
    print("ogr2ogr:", " ".join(cmd[1:]), flush=True)
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not fgb.exists():
        fgb.unlink(missing_ok=True)
        sys.exit(f"ogr2ogr 失敗: {r.stderr[-800:]}")
g = gpd.read_file(fgb)
print(f"{area.name}: bbox 内 {len(g):,} 本 ({args.source})", flush=True)

if args.source == "optimal":
    g = g.rename(columns={"vt_code": "ftCode", "vt_lvorder": "lvOrder", "vt_tollsect": "tollSect", "vt_motorway": "motorway"})
    g["rnkWidth"] = g["vt_rnkwidth"].map(RNKWIDTH)
    g["rdCtg"] = g["vt_rdctg"].map(RDCTG)
    g["medSect"] = 0  # 属性が無い
    g["orgGILvl"] = None
    g = g.drop(columns=[c for c in ("vt_rnkwidth", "vt_rdctg", "vt_drworder", "vt_flag17", "vt_width", "mvt_id") if c in g])
else:
    g = g.drop(columns=[c for c in ("mvt_id",) if c in g])
for c in ("ftCode", "rdCtg", "rnkWidth", "medSect", "motorway", "tollSect", "lvOrder"):
    if c in g:
        g[c] = pd.to_numeric(g[c], errors="coerce").astype("Int64")
g = g[g.ftCode.between(2700, 2799)]  # 道路中心線のみ(2201 道路縁などを落とす)
g["z"], g["x"], g["y"] = 16, -1, -1

gdf = g.to_crs(area.epsg)
gdf["len_all_m"] = gdf.length
city_m = gpd.GeoSeries([city], crs=4326).to_crs(area.epsg).iloc[0]
if assign == "clip":
    gdf["in_city"] = gdf.intersects(city_m)
    gdf = gdf[gdf.in_city].copy()
    gdf["geometry"] = gdf.geometry.intersection(city_m)
    gdf = gdf[~gdf.geometry.is_empty]
else:
    rep = gpd.GeoDataFrame(geometry=gdf.geometry.representative_point(), crs=gdf.crs)
    hit = gpd.sjoin(rep, gpd.GeoDataFrame(geometry=[city_m], crs=gdf.crs), how="inner", predicate="within").index
    gdf = gdf.loc[gdf.index.isin(hit)].copy()
    gdf["in_city"] = True
gdf["len_city_m"] = gdf.length
gdf["cls"] = [
    common.classify_width(int(r.ftCode), None if pd.isna(r.rdCtg) else int(r.rdCtg), None if pd.isna(r.rnkWidth) else int(r.rnkWidth),
                          None if pd.isna(r.medSect) else int(r.medSect), None if pd.isna(r.motorway) else int(r.motorway))
    for r in gdf.itertuples()
]

# 05 が読む。市区町村は従来どおり GeoJSON も出す(小さい)。都道府県は Parquet だけ(GeoJSON は 100 万本で GB 単位)
gdf.to_parquet(area.out / "roads_city.parquet")
if area.cfg.get("kind") != "prefecture":
    gdf.to_crs(4326).to_file(area.out / "roads_city.geojson", driver="GeoJSON")


def tab(df, by, col="len_city_m"):
    s_ = df.groupby(by, dropna=False)[col].sum() / 1000
    return pd.concat([s_.rename("km"), (s_ / s_.sum() * 100).rename("%").round(1)], axis=1)


pd.set_option("display.width", 200)
print(f"{area.name}: 市域内 {len(gdf):,} 本 {gdf.len_city_m.sum() / 1000:,.1f} km  (assign={assign}, source={args.source})")
cl = gdf[gdf.ftCode.between(2701, 2704)]
for col in ("rnkWidth", "medSect", "rdCtg", "motorway"):
    print(f"## {col}\n", tab(cl, col), "\n")
print("## 一次判定\n", tab(gdf, "cls"), "\n")
tab(gdf, "cls").to_csv(area.out / "summary_cls.csv")
tab(cl, ["rnkWidth", "medSect", "rdCtg", "motorway"]).to_csv(area.out / "summary_attrs.csv")
