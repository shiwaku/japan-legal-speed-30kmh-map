#!/bin/bash
# 6. out/<area>/final.geojson → docs/tiles/<area>.pmtiles
#    Z12 から作る。Z10–11 は市全域が 1 タイルに入り(札幌は 19 万本で 15MB 超)、ブラウザが固まる。
#
# tippecanoe は Windows 向け配布が無いので WSL2 で実行する:
#   wsl bash scripts/06_build_pmtiles.sh kawagoe
# Linux/macOS ならそのまま:
#   bash scripts/06_build_pmtiles.sh kawagoe
set -euo pipefail
AREA="${1:?usage: 06_build_pmtiles.sh <area>}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/out/$AREA/final.geojson"
DST="$ROOT/docs/tiles/$AREA.pmtiles"
[ -f "$SRC" ] || { echo "$SRC が無い。05_match_regulation.py --save を先に" >&2; exit 1; }

# /mnt/c (drvfs) 上での tippecanoe は遅いので、WSL では ext4 側の一時ディレクトリで作る
W="$(mktemp -d "${TMPDIR:-/tmp}/speed30.XXXXXX")"
trap 'rm -rf "$W"' EXIT
cp "$SRC" "$W/in.geojson"

tippecanoe -o "$W/out.pmtiles" --force \
  -l roads -n "japan-legal-speed-30kmh-map $AREA" \
  -A "国土地理院ベクトルタイル提供実験 / JARTIC 交通規制情報" \
  -Z12 -z16 --no-tile-size-limit --no-feature-limit \
  -y final -y cls -y rnkWidth -y medSect -y rdCtg -y ftCode -y orgGILvl \
  -y reg_speed -y zone_speed -y frac_speed -y frac_zone -y frac_lane -y len_m \
  -y speed_before -y speed_after \
  "$W/in.geojson"

mkdir -p "$(dirname "$DST")"
cp "$W/out.pmtiles" "$DST"
ls -la "$DST"
tippecanoe --version
