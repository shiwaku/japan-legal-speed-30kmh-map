"""2. tiles_z16.csv のタイルを data/gsi/tiles/<area>/ に取得する(サイズが一致する既存ファイルはスキップ)。

    uv run python scripts/02_fetch_tiles.py --area kawagoe
"""
import csv
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import requests

import common

args = common.parser(__doc__).parse_args()
area = common.Area(args.area)

sess = requests.Session()
sess.headers["User-Agent"] = "japan-legal-speed-30kmh-map (https://github.com/shiwaku/japan-legal-speed-30kmh-map)"


def fetch(row):
    z, x, y = row["z"], row["x"], row["y"]
    dst = area.tiles_dir / f"{z}_{x}_{y}.pbf"
    if dst.exists() and dst.stat().st_size == int(row["size"]):
        return "skip"
    for i in range(3):
        r = sess.get(common.GSI_TILE_URL.format(z=z, x=x, y=y), timeout=30)
        if r.status_code == 200:
            dst.write_bytes(r.content)
            return "ok"
        time.sleep(1 + i)
    return f"fail:{r.status_code}"


rows = list(csv.DictReader(open(area.tiles_csv)))
with ThreadPoolExecutor(6) as ex:  # 提供実験中のサーバーなので控えめに
    res = Counter(ex.map(fetch, rows))
print(f"{area.name}: {dict(res)} → {area.tiles_dir}")
