#!/bin/bash
# 市区町村の境界と代表点(make_municipalities.py が書く data/n03/municipalities{,_points}.fgb)
#   → viewer/public/tiles/municipalities.pmtiles (Z4–12)
# 2 レイヤー: muni(面。変更率で塗る・境界線・選択中の輪郭)と muni_pt(代表点。変更率のラベル)。
# 属性は code/name/pref_code/pref_name/lv/car_km/changed_km/pct。
#   wsl bash scripts/06_build_municipalities_pmtiles.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/data/n03/municipalities.fgb"
PTS="$ROOT/data/n03/municipalities_points.fgb"
DST="$ROOT/viewer/public/tiles/municipalities.pmtiles"
for f in "$SRC" "$PTS"; do
  [ -f "$f" ] || { echo "$f が無い。make_municipalities.py を先に" >&2; exit 1; }
done

W="$(mktemp -d "${TMPDIR:-/tmp}/speed30.XXXXXX")"
trap 'rm -rf "$W"' EXIT
# tippecanoe は FlatGeobuf を直接読める
cp "$SRC" "$W/poly.fgb"
cp "$PTS" "$W/pts.fgb"

# 低ズームでも間引かない(歯抜けだと比較にならない)。-r1 は代表点(ラベル)の間引きを止める指定で、
# 既定では低ズームほど点が 1/2.5 ずつ捨てられる
tippecanoe -o "$W/out.pmtiles" --force \
  -n "japan-legal-speed-30kmh-map municipalities" \
  -A "国土数値情報 行政区域 N03-20240101" \
  -Z4 -z12 -r1 --detect-shared-borders \
  --no-tile-size-limit --no-feature-limit \
  -y code -y name -y pref_code -y pref_name -y lv -y car_km -y changed_km -y pct \
  -L muni:"$W/poly.fgb" -L muni_pt:"$W/pts.fgb"

mkdir -p "$(dirname "$DST")"
cp "$W/out.pmtiles" "$DST"
ls -la "$DST"
