#!/bin/bash
# 実験: GDAL の PMTiles/MVT ドライバで最適化ベクトルタイルの RdCL を ZL16 で読めるか(川越 bbox、リモート)。
set -euo pipefail
SRC="${1:-/vsicurl/https://cyberjapandata.gsi.go.jp/xyz/optimal_bvmap-v1/optimal_bvmap-v1.pmtiles}"
OUT="${2:-/tmp/kawagoe_rdcl_gdal.fgb}"
# ogrinfo -so は全タイルを走査して件数を数えようとして終わらないので使わない
echo "[ogr2ogr start] $(date +%T)"
ogr2ogr -f FlatGeobuf "$OUT" "$SRC" RdCL -oo ZOOM_LEVEL=16 -oo CLIP=YES -spat 139.377 35.837 139.559 35.963 -spat_srs EPSG:4326 -t_srs EPSG:4326
echo "[done] $(date +%T)"; ls -la "$OUT"
ogrinfo -ro -so "$OUT" 2>&1 | grep -E "Feature Count"
