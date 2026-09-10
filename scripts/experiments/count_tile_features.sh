#!/bin/bash
# 実験: PMTiles の各ズームのタイルに何本入っているか数える(低ズームのまとめ・間引きの確認)
#   wsl bash scripts/experiments/count_tile_features.sh docs/tiles/sapporo.pmtiles "9 457 188" "10 914 376" "12 3656 1505"
set -euo pipefail
F="$1"; shift
for t in "$@"; do
  set -- $t
  n=$(tippecanoe-decode "$F" "$1" "$2" "$3" | grep -c '"type": "Feature"' || true)
  b=$(tippecanoe-decode "$F" "$1" "$2" "$3" | wc -c)
  echo "z$1/$2/$3 features=$n geojson_bytes=$b"
done
