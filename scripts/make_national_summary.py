"""全国版の集計: viewer/public/areas.json の 47 都道府県から全国合計を作り、都道府県一覧(CSV/Markdown)を出す。

- viewer/public/areas.json の pref_XX に kind / pref_code / tiles(全国 PMTiles の URL) を補い、"japan" エントリ(全国合計)を足す
- out/national/prefectures.csv, out/national/prefectures.md: 都道府県別の 60→30 割合と道路統計との比較

    uv run python scripts/make_national_summary.py --tiles https://.../japan-legal-speed-30kmh.pmtiles
"""
import argparse
import datetime as dt
import json

import pandas as pd

import common

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--tiles", default=None, help="全国 PMTiles の URL(R2 など)。都道府県エリアの表示に使う。未指定なら既存値を保つ")
args = p.parse_args()

manifest_path = common.DOCS / "areas.json"
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
prefs = {}
for f in sorted(common.AREAS.glob("pref_*.json")):
    cfg = json.loads(f.read_text(encoding="utf-8"))
    key = f.stem
    if key not in manifest:
        print(f"{key} {cfg['name']}: 未処理(viewer/public/areas.json に無い)")
        continue
    m = manifest[key]
    m["kind"] = "prefecture"
    m["pref_code"] = cfg["pref_code"]
    m["view"] = cfg["view"]  # areas/*.json 側を正とする(初期表示位置を直したら 05 を回さなくても反映)
    m["official_width"] = cfg.get("official_width")
    if args.tiles:
        m["tiles"] = args.tiles
    prefs[key] = (cfg, m)

if not prefs:
    raise SystemExit("都道府県の結果が無い")

# ---- 全国合計 -----------------------------------------------------------------
def ssum(k):
    return sum(m["classes"].get(k, 0) for _, m in prefs.values())

classes = {}
for _, m in prefs.values():
    for k, v in m["classes"].items():
        classes[k] = classes.get(k, 0) + v
speed_before, speed_after = {}, {}
for _, m in prefs.values():
    for k, v in (m.get("speed_before") or {}).items():
        speed_before[k] = speed_before.get(k, 0) + v
    for k, v in (m.get("speed_after") or {}).items():
        speed_after[k] = speed_after.get(k, 0) + v
total = sum(m["total_km"] for _, m in prefs.values())
official_total = sum(m["official"]["official_total_km"] for _, m in prefs.values() if m.get("official"))
gsi_normal = sum(m["official"]["gsi_normal_total_km"] for _, m in prefs.values() if m.get("official"))
excess = sum(m["official"]["excess_km"] for _, m in prefs.values() if m.get("official"))
changed = classes.get(common.FINAL_CHANGED, 0)
structural = sum(m["official"]["structural_share_pct"][1] / 100 * m["official"]["gsi_normal_total_km"] for _, m in prefs.values() if m.get("official"))
rng = lambda x: [round((x - excess) / (gsi_normal - excess) * 100, 1), round(x / gsi_normal * 100, 1)]
manifest["japan"] = {
    "name": f"全国({len(prefs)} 都道府県)",
    "kind": "japan",
    "view": {"center": [137.5, 37.5], "zoom": 5},
    "tiles": args.tiles or manifest.get("japan", {}).get("tiles"),
    "jartic_month": next(iter(prefs.values()))[1]["jartic_month"],
    "buffer_m": next(iter(prefs.values()))[1]["buffer_m"],
    "generated": dt.date.today().isoformat(),
    "total_km": round(total, 1),
    "classes": {k: round(v, 1) for k, v in sorted(classes.items(), key=lambda kv: -kv[1])},
    "speed_before": {k: round(v, 1) for k, v in speed_before.items()},
    "speed_after": {k: round(v, 1) for k, v in speed_after.items()},
    "official": {
        "source": "国土交通省 道路統計年報 2024(都道府県別の合計)", "as_of": "2023-03-31",
        "official_total_km": round(official_total, 1), "gsi_normal_total_km": round(gsi_normal, 1), "excess_km": round(excess, 1),
        "structural_share_pct": rng(structural), "changed_share_pct": rng(changed),
    },
}
# 並び: 全国 → 都道府県(コード順) → 市区町村
ordered = {"japan": manifest["japan"]}
ordered.update({k: manifest[k] for k in sorted(prefs, key=lambda k: prefs[k][0]["pref_code"])})
ordered.update({k: v for k, v in manifest.items() if k not in ordered})
manifest_path.write_text(json.dumps(ordered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

# ---- 都道府県一覧 -------------------------------------------------------------
rows = []
for key, (cfg, m) in sorted(prefs.items(), key=lambda kv: kv[1][0]["pref_code"]):
    o = m.get("official") or {}
    normal = o.get("gsi_normal_total_km") or m["total_km"]
    ch = m["classes"].get(common.FINAL_CHANGED, 0)
    rows.append({
        "code": cfg["pref_code"], "都道府県": cfg["name"],
        "地理院中心線 km": m["total_km"], "車道 km": normal, "60→30 変更 km": ch,
        "変更/車道 %": round(ch / normal * 100, 1),
        "変更/道路法道路 %(下限〜上限)": f"{o.get('changed_share_pct', ['?', '?'])[0]}〜{o.get('changed_share_pct', ['?', '?'])[1]}",
        "対象道路 %(下限〜上限)": f"{o.get('structural_share_pct', ['?', '?'])[0]}〜{o.get('structural_share_pct', ['?', '?'])[1]}",
        "道路統計 5.5m未満 %": (cfg.get("official_width") or {}).get("share_lt_5_5m_pct"),
        "道路統計 実延長 km": o.get("official_total_km"), "地理院 市区町村道の超過 km": (o.get("excess_detail") or {}).get("市区町村道の超過"),
    })
df = pd.DataFrame(rows)
outdir = common.OUT / "national"
outdir.mkdir(parents=True, exist_ok=True)
df.to_csv(outdir / "prefectures.csv", index=False, encoding="utf-8-sig")
md = ["| " + " | ".join(df.columns) + " |", "|" + "---|" * len(df.columns)]
for r in df.itertuples(index=False):
    md.append("| " + " | ".join(f"{v:,.0f}" if isinstance(v, float) and abs(v) >= 100 else str(v) for v in r) + " |")
(outdir / "prefectures.md").write_text("\n".join(md) + "\n", encoding="utf-8")

j = manifest["japan"]
print(f"全国 {len(prefs)} 都道府県: 中心線 {total:,.0f} km / 車道 {gsi_normal:,.0f} km / 道路統計 {official_total:,.0f} km")
print(f"  60→30 変更 {changed:,.0f} km = 車道の {changed / gsi_normal * 100:.1f}% / 道路法道路に換算 {j['official']['changed_share_pct'][0]}〜{j['official']['changed_share_pct'][1]}%")
print(f"  構造的に対象(5.5m未満・分離帯なし) 道路法道路に換算 {j['official']['structural_share_pct'][0]}〜{j['official']['structural_share_pct'][1]}%  (道路統計年報の 5.5m 未満 = 71.0%)")
print(f"  → {outdir / 'prefectures.csv'}, {manifest_path}")
