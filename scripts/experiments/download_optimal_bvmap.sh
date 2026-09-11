#!/bin/bash
# 地理院 最適化ベクトルタイル(全国 1 本の PMTiles, 約 17GB)を WSL の ext4 側に落とす。再開可(-C -)。
#   wsl bash scripts/experiments/download_optimal_bvmap.sh
set -euo pipefail
D="$HOME/gsi"; mkdir -p "$D"
URL="https://cyberjapandata.gsi.go.jp/xyz/optimal_bvmap-v1/optimal_bvmap-v1.pmtiles"
echo "[start] $(date +%T)"
curl -sS -L -C - -o "$D/optimal_bvmap-v1.pmtiles" "$URL" || curl -sS -L -C - -o "$D/optimal_bvmap-v1.pmtiles" "$URL"
ls -la "$D/optimal_bvmap-v1.pmtiles"
echo "[done] $(date +%T)"
