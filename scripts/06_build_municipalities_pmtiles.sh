#!/bin/bash
# 市区町村境界(make_municipalities.py が書く data/n03/municipalities.fgb) → viewer/public/tiles/municipalities.pmtiles
# ビューワで選んだ市区町村の輪郭を出すためだけの薄いタイル(Z4–12、属性は code/name/pref_code)。
#   wsl bash scripts/06_build_municipalities_pmtiles.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/data/n03/municipalities.fgb"
DST="$ROOT/viewer/public/tiles/municipalities.pmtiles"
[ -f "$SRC" ] || { echo "$SRC が無い。make_municipalities.py を先に" >&2; exit 1; }

W="$(mktemp -d "${TMPDIR:-/tmp}/speed30.XXXXXX")"
trap 'rm -rf "$W"' EXIT
# tippecanoe は FlatGeobuf を直接読める
cp "$SRC" "$W/in.fgb"

tippecanoe -o "$W/out.pmtiles" --force \
  -l muni -n "japan-legal-speed-30kmh-map municipalities" \
  -A "国土数値情報 行政区域 N03-20240101" \
  -Z4 -z12 --detect-shared-borders --coalesce-densest-as-needed --extend-zooms-if-still-dropping \
  -y code -y name -y pref_code \
  "$W/in.fgb"

mkdir -p "$(dirname "$DST")"
cp "$W/out.pmtiles" "$DST"
ls -la "$DST"
