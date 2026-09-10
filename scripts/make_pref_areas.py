"""47 都道府県のエリア定義を作る。

- 市域: 国土数値情報 N03-20240101(全国) を都道府県で結合 → data/areas/pref_<code>/boundary.geojson
- 道路統計: data/official/prefectures.json(make_pref_official.py) → official_road_km
- EPSG: 都道府県ごとの平面直角座標系(北海道は XII 系、鹿児島は II 系など代表 1 系で長さを測る)

    uv run python scripts/make_pref_areas.py            # 47 都道府県
    uv run python scripts/make_pref_areas.py 11 13      # 一部だけ
"""
import json
import sys
import zipfile

import geopandas as gpd

import common

N03_ZIP = common.DATA / "n03" / "N03-20240101_GML.zip"
OFFICIAL = common.DATA / "official" / "prefectures.json"

# 平面直角座標系(JGD2011)。I=6669 … XIX=6687。県内で最も面積の大きい系を 1 つ選ぶ
EPSG = {
    "01": 6680, "02": 6678, "03": 6678, "04": 6678, "05": 6678, "06": 6678, "07": 6677, "08": 6677, "09": 6677, "10": 6677,
    "11": 6677, "12": 6677, "13": 6677, "14": 6677, "15": 6676, "16": 6675, "17": 6675, "18": 6674, "19": 6676, "20": 6676,
    "21": 6675, "22": 6676, "23": 6675, "24": 6674, "25": 6674, "26": 6674, "27": 6674, "28": 6673, "29": 6674, "30": 6674,
    "31": 6673, "32": 6671, "33": 6673, "34": 6671, "35": 6671, "36": 6672, "37": 6672, "38": 6672, "39": 6672, "40": 6670,
    "41": 6670, "42": 6669, "43": 6670, "44": 6670, "45": 6670, "46": 6670, "47": 6683,
}
ZONE = {6669: "I", 6670: "II", 6671: "III", 6672: "IV", 6673: "V", 6674: "VI", 6675: "VII", 6676: "VIII", 6677: "IX",
        6678: "X", 6679: "XI", 6680: "XII", 6681: "XIII", 6682: "XIV", 6683: "XV"}

want = set(sys.argv[1:]) or set(EPSG)
official = json.loads(OFFICIAL.read_text(encoding="utf-8"))

with zipfile.ZipFile(N03_ZIP) as z:
    shp = [n for n in z.namelist() if n.endswith(".shp") and "subprefecture" not in n][0]
n03 = gpd.read_file(f"zip://{N03_ZIP}!{shp}", encoding="utf-8")
n03["pref_code"] = n03["N03_007"].astype(str).str[:2]
print(f"N03: {len(n03)} polygons")

for code in sorted(want):
    sub = n03[n03.pref_code == code]
    if sub.empty:
        print(code, "N03 に無い"); continue
    pname = sub["N03_001"].iloc[0]
    d = gpd.GeoDataFrame({"name": [pname], "pref_code": [code], "source": ["国土数値情報 N03-20240101 (市区町村を結合)"]},
                         geometry=[sub.union_all()], crs=n03.crs).to_crs(4326)
    key = f"pref_{code}"
    out = common.DATA / "areas" / key
    out.mkdir(parents=True, exist_ok=True)
    d.to_file(out / "boundary.geojson", driver="GeoJSON")
    w, s, e, n = d.total_bounds
    epsg = EPSG[code]
    o = official[code]
    area = {
        "name": pname,
        "kind": "prefecture",
        "pref_code": code,
        "epsg": epsg,
        "_comment_epsg": f"平面直角座標系 {ZONE.get(epsg, '?')} 系。県全域を 1 系で測る",
        "_comment_boundary": "data/areas/<key>/boundary.geojson は国土数値情報 N03-20240101 の市区町村を結合したもの(make_pref_areas.py)",
        "gsi_source": "experimental_bvmap",
        "_comment_gsi": "地理院ベクトルタイル提供実験 ZL16 を全国分ダウンロードし(download_tiles_all.sh)、GDAL の MVT ドライバでディレクトリごと抽出(03_extract_roads_gdal.py)。市区町村版と同じ属性(medSect あり)",
        "official_road_km": {
            "_comment": "道路法上の道路の実延長(道路統計年報 2024 表19/22/25、高速は表15合計との差)。make_pref_official.py で生成",
            "source": o["official_road_km"]["source"],
            "as_of": o["official_road_km"]["as_of"],
            "高速自動車国道等": o["official_road_km"]["高速自動車国道等"],
            "国道": o["official_road_km"]["国道"],
            "都道府県道": o["official_road_km"]["都道府県道"],
            "市区町村道": o["official_road_km"]["市区町村道"],
        },
        "official_width": {"_comment": "道路統計年報 表15 の幅員別実延長(km)と 5.5m 未満の割合", **o["width_km"], "share_lt_5_5m_pct": o["share_lt_5_5m_pct"]},
        "view": {"center": [round((w + e) / 2, 4), round((s + n) / 2, 4)], "zoom": 9},
    }
    (common.AREAS / f"{key}.json").write_text(json.dumps(area, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{key} {pname} EPSG:{epsg} area {d.to_crs(epsg).area.sum() / 1e6:,.0f} km2 official {o['official_road_km']['合計']:,.0f} km")
