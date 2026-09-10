#!/bin/bash
# 全国版(B): make_tile_download_list.py が作ったリストを aria2c で 8 並列取得する(WSL、ext4 側に保存)。
# 中断したら make_tile_download_list.py を再実行してから、もう一度これを走らせれば残りだけ落ちる。
#   wsl bash scripts/download_tiles_all.sh
set -euo pipefail
LISTS=/mnt/c/Users/yshiw/Documents/GIS/japan-legal-speed-30kmh-map/data/gsi/experimental_lists
D="$HOME/gsi/experimental_bvmap"; mkdir -p "$D"
echo "[start] $(date '+%F %T')"
for f in "$LISTS"/part_*.txt; do
  echo "[$(basename "$f")] $(date +%T)"
  aria2c -i "$f" -d "$D" \
    --max-concurrent-downloads=8 --max-connection-per-server=8 --split=1 \
    --allow-overwrite=true --auto-file-renaming=false --remote-time=true \
    --max-tries=5 --retry-wait=3 --timeout=30 --connect-timeout=15 \
    --user-agent="japan-legal-speed-30kmh-map (https://github.com/shiwaku/japan-legal-speed-30kmh-map)" \
    --console-log-level=warn --summary-interval=0 --download-result=hide \
    || echo "  [warn] aria2c rc=$? on $(basename "$f") (残りは再実行で取れる)"
done
echo "[done] $(date '+%F %T')"
find "$D/16" -name '*.pbf' | wc -l
du -sh "$D"
