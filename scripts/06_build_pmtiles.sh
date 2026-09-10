#!/bin/bash
# 6. out/<area>/final.geojson → docs/tiles/<area>.pmtiles
#
# 2 段で作って tile-join で 1 本にする。
#   Z9–11 (概観): 属性を final / speed_before / speed_after の 3 つに絞り、同じ属性の線分を
#                1 本の MultiLineString にまとめる(--reorder --coalesce)。線分は落とさない。
#                市全域が 1〜数タイルに入るので、そのままだと札幌 19 万本で 1 タイル 15MB 超になり
#                ブラウザが固まるが、重いのは本数(フィーチャごとの処理)で、頂点数ではない。
#                本数上限で落とすと道路網が歯抜けになるので、まとめる方式にした。
#   Z12–16 (詳細): 全線分・全属性。クリックで判定根拠を見るのはこちら。
# 低ズームは概観用で、集計は out/ の値を使う。
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
NAME="japan-legal-speed-30kmh-map $AREA"
ATTR="国土地理院ベクトルタイル提供実験 / JARTIC 交通規制情報"

tippecanoe -o "$W/low.pmtiles" --force -l roads -n "$NAME" -A "$ATTR" \
  -Z9 -z11 --no-feature-limit --no-tile-size-limit \
  --reorder --coalesce --reverse --simplification=8 \
  -y final -y speed_before -y speed_after \
  "$W/in.geojson"

tippecanoe -o "$W/high.pmtiles" --force -l roads -n "$NAME" -A "$ATTR" \
  -Z12 -z16 --no-tile-size-limit --no-feature-limit \
  -y final -y cls -y rnkWidth -y medSect -y rdCtg -y ftCode -y orgGILvl \
  -y reg_speed -y zone_speed -y frac_speed -y frac_zone -y frac_lane -y len_m \
  -y speed_before -y speed_after \
  "$W/in.geojson"

tile-join -o "$W/out.pmtiles" --force -pk -n "$NAME" -A "$ATTR" "$W/low.pmtiles" "$W/high.pmtiles"

mkdir -p "$(dirname "$DST")"
cp "$W/out.pmtiles" "$DST"
ls -la "$DST"
tippecanoe --version
