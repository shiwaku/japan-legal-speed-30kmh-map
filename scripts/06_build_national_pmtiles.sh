#!/bin/bash
# 6'. 全国版: out/pref_XX/final.fgb(47 都道府県) を 1 本の PMTiles にする。
#     Z12–16 を全線分・全属性で作る(間引き・まとめはしない)。
#     Z9 から作ると東京圏の z9 タイルが 197 万本・gzip 38MB(1 画面で 100MB 超)になりブラウザが開けないので、
#     全国版は Z12 から。市区町村版(docs/tiles/*.pmtiles)は Z9 から。
#     出来上がりは 5GB 超になる見込みなので docs/ には置かず ~/gsi/ に出し、R2 などへ上げる。
#
#   wsl bash scripts/06_build_national_pmtiles.sh            # ~/gsi/japan-legal-speed-30kmh.pmtiles
#   wsl bash scripts/06_build_national_pmtiles.sh /path/out.pmtiles
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DST="${1:-$HOME/gsi/japan-legal-speed-30kmh.pmtiles}"
W="$(mktemp -d "${TMPDIR:-/tmp}/speed30-national.XXXXXX")"
trap 'rm -rf "$W"' EXIT

# drvfs 越しは遅いので入力を ext4 側にコピーしてから読む
n=0
for f in "$ROOT"/out/pref_*/final.fgb; do cp "$f" "$W/$(basename "$(dirname "$f")").fgb"; n=$((n+1)); done
echo "都道府県 $n 件 → $DST  $(date '+%F %T')"
[ "$n" -gt 0 ] || { echo "out/pref_XX/final.fgb が無い。run_prefectures.py を先に" >&2; exit 1; }

tippecanoe -o "$W/out.pmtiles" --force \
  -l roads -n "japan-legal-speed-30kmh-map (全国)" \
  -A "国土地理院ベクトルタイル提供実験 / JARTIC 交通規制情報 / 国土交通省 道路統計年報" \
  -Z12 -z16 --no-tile-size-limit --no-feature-limit \
  --read-parallel \
  -y final -y cls -y rnkWidth -y medSect -y rdCtg -y ftCode -y orgGILvl \
  -y reg_speed -y zone_speed -y len_m -y speed_before -y speed_after \
  "$W"/pref_*.fgb

mkdir -p "$(dirname "$DST")"
cp "$W/out.pmtiles" "$DST"
ls -la "$DST"
tippecanoe --version
echo "done $(date '+%F %T')"
