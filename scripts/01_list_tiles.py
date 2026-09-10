"""1. 市域と交差する地理院ベクトルタイル(experimental_bvmap) ZL16 タイルを mokuroku から列挙する。

    uv run python scripts/01_list_tiles.py --area kawagoe
"""
import csv
import gzip

import mercantile
import requests
from shapely.geometry import box

import common

args = common.parser(__doc__).parse_args()
area = common.Area(args.area)
city = area.geometry()

mokuroku = common.DATA / "gsi" / "mokuroku.csv.gz"
if not mokuroku.exists():
    mokuroku.parent.mkdir(parents=True, exist_ok=True)
    print("mokuroku.csv.gz を取得(約 75MB)...")
    with requests.get(common.GSI_MOKUROKU_URL, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(mokuroku, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)

# bbox 内のタイルのうち、市域ポリゴンと実際に交差するものだけ残す
w, s, e, n = city.bounds
want = {}
for t in mercantile.tiles(w, s, e, n, common.GSI_ZOOM):
    b = mercantile.bounds(t)
    if city.intersects(box(b.west, b.south, b.east, b.north)):
        want[f"{t.z}/{t.x}/{t.y}.pbf"] = t

rows = []
with gzip.open(mokuroku, "rt") as f:
    for path, mtime, size, md5 in csv.reader(f):
        if path in want:
            t = want[path]
            rows.append((t.z, t.x, t.y, int(size), md5))

with open(area.tiles_csv, "w", newline="") as f:
    wr = csv.writer(f)
    wr.writerow(["z", "x", "y", "size", "md5"])
    wr.writerows(rows)

print(
    f"{area.name}: 市域と交差するタイル {len(want)}、mokuroku に存在 {len(rows)}、"
    f"計 {sum(r[3] for r in rows) / 1e6:.1f} MB → {area.tiles_csv}"
)
