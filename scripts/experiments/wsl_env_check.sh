#!/bin/bash
# WSL 側の環境確認 + 川越の既取得タイルを z/x/y 配置にして GDAL MVT ディレクトリ読みを試す
set -euo pipefail
python3 -c "import aiohttp; print('aiohttp', aiohttp.__version__)" 2>&1 || true
python3 -c "import httpx; print('httpx', httpx.__version__)" 2>&1 || true
which aria2c || echo "no aria2c"
D="$HOME/gsi/experimental_bvmap"; mkdir -p "$D/16"
SRC=/mnt/c/Users/yshiw/Documents/GIS/japan-legal-speed-30kmh-map/data/gsi/tiles/kawagoe
n=0; for f in "$SRC"/16_*.pbf; do b=$(basename "$f" .pbf); IFS=_ read -r z x y <<< "$b"; mkdir -p "$D/$z/$x"; cp "$f" "$D/$z/$x/$y.pbf"; n=$((n+1)); done; echo "copied $n tiles"
echo "[ogr2ogr dir start] $(date +%T)"
ogr2ogr -f FlatGeobuf /tmp/kawagoe_exp_dir.fgb "$D" road -oo ZOOM_LEVEL=16 -oo CLIP=YES -spat 139.377 35.837 139.559 35.963 -spat_srs EPSG:4326 -t_srs EPSG:4326 -nlt MULTILINESTRING -skipfailures 2>&1 | tail -3 || true
echo "[done] $(date +%T)"; ls -la /tmp/kawagoe_exp_dir.fgb 2>/dev/null || echo "no output"
ogrinfo -ro -al -so /tmp/kawagoe_exp_dir.fgb 2>/dev/null | grep -E "Feature Count|^[a-zA-Z]+: (Integer|String|Real)" | head -12
