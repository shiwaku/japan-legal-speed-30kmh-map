"""判定済みの out/<key>/final.parquet から、viewer/public/areas.json の official(道路法上の道路への
換算)だけを作り直す。

道路統計(areas/<key>.json の official_road_km)を直したときに使う。判定そのものは変わらないので
03〜05 を回し直す必要はなく、47 都道府県で数分で終わる(05 の回し直しは約 5 時間)。
タイル(PMTiles)にも入らない値なので、この後は make_national_summary.py だけ流せばよい。

    uv run python scripts/update_official.py                 # areas.json にある全エリア
    uv run python scripts/update_official.py --area pref_14  # 1 エリアだけ
"""
import argparse
import json

import pandas as pd

import common

p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
p.add_argument("--area", help="areas/<key>.json の key。省略で areas.json にある全エリア")
args = p.parse_args()

manifest_path = common.DOCS / "areas.json"
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
keys = [args.area] if args.area else [k for k in manifest if (common.AREAS / f"{k}.json").exists()]

changed = 0
for key in keys:
    area = common.Area(key)
    src = area.out / "final.parquet"
    if key not in manifest:
        print(f"{key}: areas.json に無い(先に 05 --save)"); continue
    if not src.exists():
        print(f"{key}: {src} が無い"); continue
    official = area.cfg.get("official_road_km")
    if not official:
        print(f"{key}: official_road_km が無い"); continue
    # 幾何は要らないので pandas で読む(全国 47 県で 2 分ほど)
    roads = pd.read_parquet(src, columns=["ftCode", "rdCtg", "len_m", "cls", "final"])
    _, official_out = common.official_compare(roads[roads.ftCode.between(2701, 2704)], official)
    before = manifest[key].get("official") or {}
    manifest[key]["official"] = official_out
    if list(before.get("changed_share_pct") or []) != list(official_out["changed_share_pct"]):  # JSON は list、計算結果は tuple
        changed += 1
    print(f"{key} {area.name}: 道路統計 {official_out['official_total_km']:,.0f} km / 超過 {official_out['excess_km']:,.0f} km"
          f" → 構造的に対象 {official_out['structural_share_pct'][0]}〜{official_out['structural_share_pct'][1]}%"
          f" / 60→30 変更 {official_out['changed_share_pct'][0]}〜{official_out['changed_share_pct'][1]}%"
          f"  (前: {before.get('changed_share_pct', ['?', '?'])[0]}〜{before.get('changed_share_pct', ['?', '?'])[1]}%)", flush=True)

manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"\n{len(keys)} エリア中 {changed} エリアの割合が変わった → {manifest_path}")
print("全国合計と都道府県一覧は make_national_summary.py で作り直す")
