#!/bin/bash
D="$HOME/gsi/experimental_bvmap"
echo "--- metadata.json:"; cat "$D/metadata.json"; echo
echo "--- ogrinfo MVT:dir"; ogrinfo -ro -so "MVT:$D" 2>&1 | head -20
echo "--- ogrinfo dir/16 (zoom dir)"; ogrinfo -ro -so "MVT:$D/16" 2>&1 | head -8
echo "--- ogrinfo single tile"; ogrinfo -ro -so "$D/16/58161/25761.pbf" 2>&1 | head -8
echo "--- gdal version / MVT open options"; ogrinfo --format MVT 2>&1 | grep -A40 "Open options" | head -30
