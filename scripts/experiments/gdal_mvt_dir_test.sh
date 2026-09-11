#!/bin/bash
# 実験: z/x/y に置いた experimental_bvmap タイルを GDAL MVT ドライバでディレクトリとして読む(metadata.json が要る)
set -euo pipefail
D="$HOME/gsi/experimental_bvmap"
cat > "$D/metadata.json" <<'JSON'
{"name":"experimental_bvmap","format":"pbf","minzoom":"16","maxzoom":"16","bounds":"122.0,20.0,154.0,46.0","scheme":"xyz",
 "json":"{\"vector_layers\":[{\"id\":\"road\",\"fields\":{\"ftCode\":\"Number\",\"rdCtg\":\"Number\",\"rnkWidth\":\"Number\",\"medSect\":\"Number\",\"motorway\":\"Number\",\"tollSect\":\"Number\",\"lvOrder\":\"Number\",\"orgGILvl\":\"String\"}}]}"}
JSON
echo "[ogr2ogr start] $(date +%T)"
rm -f /tmp/kawagoe_exp_dir.fgb
ogr2ogr -f FlatGeobuf /tmp/kawagoe_exp_dir.fgb "MVT:$D/16" road -oo ZOOM_LEVEL=16 -oo CLIP=YES -spat 139.377 35.837 139.559 35.963 -spat_srs EPSG:4326 -t_srs EPSG:4326 -nlt MULTILINESTRING -skipfailures 2>&1 | grep -v "^Warning 6" | tail -3 || true
echo "[done] $(date +%T)"; ls -la /tmp/kawagoe_exp_dir.fgb 2>/dev/null || echo "no output"
ogrinfo -ro -al -so /tmp/kawagoe_exp_dir.fgb 2>/dev/null | grep -E "Feature Count|^[a-zA-Z]+: (Integer|String|Real)" | head -12
cp /tmp/kawagoe_exp_dir.fgb /mnt/c/Users/yshiw/Documents/GIS/japan-legal-speed-30kmh-map/data/gsi/ 2>/dev/null || true
