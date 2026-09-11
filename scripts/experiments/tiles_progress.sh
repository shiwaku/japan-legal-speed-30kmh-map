#!/bin/bash
# 全国タイル取得の進捗(件数・容量・aria2 ログ末尾)
D="$HOME/gsi/experimental_bvmap"
n=$(find "$D/16" -name '*.pbf' 2>/dev/null | wc -l)
echo "$(date +%T) tiles=$n / 2,159,184 ($(( n * 100 / 2159184 ))%)  size=$(du -sh "$D" 2>/dev/null | cut -f1)"
tail -n 3 /mnt/c/Users/yshiw/Documents/GIS/japan-legal-speed-30kmh-map/data/gsi/experimental_download.log 2>/dev/null
