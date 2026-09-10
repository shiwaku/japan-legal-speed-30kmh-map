"""実験: OSM の highway 種別を地理院中心線に当てて、道路法適用外(私道・農道)を切り分けられるか。

Overpass で市域の highway=* を取り、GSI 線分ごとに 10 m バッファ内で最も重なる OSM way の
highway / access を付与。service / track / path / access=private を「適用外の疑い」とみなし、
その合計が道路統計との差(川越 657 km)にどれだけ近いかを見る。
"""
import json, sys, time
from pathlib import Path
import geopandas as gpd, pandas as pd, requests, shapely
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import common

area = common.Area(sys.argv[1] if len(sys.argv) > 1 else "kawagoe")
city = area.geometry()
cache = area.data / "osm_highways.geojson"
if not cache.exists():
    w, s, e, n = city.bounds
    q = f'[out:json][timeout:180];way["highway"]({s},{w},{n},{e});out geom;'
    hdr = {"User-Agent": "japan-legal-speed-30kmh-map/experiment (https://github.com/shiwaku/japan-legal-speed-30kmh-map)"}
    for ep in ("https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"):
        r = requests.post(ep, data={"data": q}, headers=hdr, timeout=240)
        if r.ok: break
        print(ep, r.status_code)
    r.raise_for_status()
    feats = []
    for el in r.json()["elements"]:
        if el.get("type") != "way" or len(el.get("geometry", [])) < 2: continue
        t = el.get("tags", {})
        feats.append({"type": "Feature", "properties": {"highway": t.get("highway"), "access": t.get("access"), "service": t.get("service"), "name": t.get("name"), "osm_id": el["id"]},
                      "geometry": {"type": "LineString", "coordinates": [[p["lon"], p["lat"]] for p in el["geometry"]]}})
    cache.write_text(json.dumps({"type": "FeatureCollection", "features": feats}, ensure_ascii=False), encoding="utf-8")
    print(f"Overpass: {len(feats)} ways → {cache}")
osm = gpd.read_file(cache).to_crs(area.epsg)
osm = osm[osm.intersects(gpd.GeoSeries([city], crs=4326).to_crs(area.epsg).iloc[0])].reset_index(drop=True)
osm["osm_len_m"] = osm.length
print("OSM highway 別 km:\n", (osm.groupby("highway").osm_len_m.sum() / 1000).round(1).sort_values(ascending=False).head(15).to_string())

roads = gpd.read_parquet(area.out / "final.parquet")
roads = roads[roads.ftCode.between(2701, 2704)].reset_index(drop=True)
roads["seg_id"] = roads.index
buf = osm[["highway", "access", "service", "geometry"]].copy(); buf["geometry"] = buf.geometry.buffer(10, cap_style="flat")
j = gpd.sjoin(roads[["seg_id", "len_m", "geometry"]], buf, how="inner", predicate="intersects")
inter = shapely.intersection(j.geometry.values, buf.geometry.values[j.index_right.values])
j["ol"] = shapely.length(inter)
j = j.sort_values("ol", ascending=False).drop_duplicates("seg_id")
j["frac"] = (j.ol / j.len_m).clip(upper=1)
j.loc[j.frac < 0.5, ["highway", "access", "service"]] = ["(unmatched)", None, None]
roads = roads.merge(j[["seg_id", "highway", "access", "service", "frac"]], on="seg_id", how="left")
roads["highway"] = roads.highway.fillna("(unmatched)")

def suspect(r):
    if r.highway in ("service", "track", "path", "footway", "pedestrian", "steps", "cycleway", "bridleway"): return True
    if r.access in ("private", "no"): return True
    return False
roads["non_road_law"] = [suspect(r) for r in roads.itertuples()]
pd.set_option("display.width", 200)
print("\nGSI 通常道路 km × OSM highway:\n", (roads.groupby("highway").len_m.sum() / 1000).round(1).sort_values(ascending=False).to_string())
print("\n適用外の疑い(service/track/path/access=private): %.0f km  ← 道路統計との差 %s km" % (roads.loc[roads.non_road_law, "len_m"].sum() / 1000, area.cfg.get("official_road_km", {}).get("市区町村道") and round(roads.loc[roads.rdCtg == 2, "len_m"].sum() / 1000 - area.cfg["official_road_km"]["市区町村道"], 0)))
print("(unmatched) km: %.0f  / うち幅員3m未満: %.0f" % (roads.loc[roads.highway == "(unmatched)", "len_m"].sum() / 1000, roads.loc[(roads.highway == "(unmatched)") & (roads.rnkWidth == 0), "len_m"].sum() / 1000))
print("\n判定クラス × 適用外の疑い km:\n", (roads.pivot_table(index="final", columns="non_road_law", values="len_m", aggfunc="sum", fill_value=0) / 1000).round(1).to_string())
print("\nrnkWidth × OSM highway km:\n", (roads.pivot_table(index="rnkWidth", columns="highway", values="len_m", aggfunc="sum", fill_value=0) / 1000).round(0).to_string())
