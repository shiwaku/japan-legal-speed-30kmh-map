"""全国版(B): experimental_bvmap の ZL16 タイル全件を mokuroku から列挙し、aria2c 用の入力リストを作る。

既に WSL 側 ~/gsi/experimental_bvmap/16/x/y.pbf にあり、サイズが mokuroku と一致するものは除く(再開用)。
出力は data/gsi/experimental_lists/part_NNN.txt(1 ファイル 10 万タイル)。取得は scripts/download_tiles_all.sh。

    uv run python scripts/make_tile_download_list.py
"""
import csv
import gzip
import os
import subprocess

import common

MOKUROKU = common.DATA / "gsi" / "mokuroku.csv.gz"
LISTS = common.DATA / "gsi" / "experimental_lists"
WSL_ROOT = os.environ.get("EXPERIMENTAL_TILES_WSL", "/home/shi-works/gsi/experimental_bvmap")
CHUNK = 100_000

LISTS.mkdir(parents=True, exist_ok=True)
for old in LISTS.glob("part_*.txt"):
    old.unlink()

# 取得済みの一覧は WSL 側で find する(\\wsl.localhost 越しに 200 万回 stat すると終わらない)
r = subprocess.run(["wsl", "bash", "-c", f"mkdir -p {WSL_ROOT}/16 && cd {WSL_ROOT} && find 16 -name '*.pbf' -printf '%p %s\\n'"],
                   capture_output=True, text=True)
have_size = {}
for line in r.stdout.splitlines():
    p, sz = line.rsplit(" ", 1)
    have_size[p] = int(sz)
print(f"WSL 側の既存タイル: {len(have_size):,}")

have = 0
missing = []
total_bytes = 0
with gzip.open(MOKUROKU, "rt") as f:
    for path, mtime, size, md5 in csv.reader(f):
        if not path.startswith("16/"):
            continue
        if have_size.get(path) == int(size):
            have += 1
            continue
        missing.append((path, int(size)))
        total_bytes += int(size)

for i in range(0, len(missing), CHUNK):
    with open(LISTS / f"part_{i // CHUNK:03d}.txt", "w", newline="\n") as f:
        for path, size in missing[i:i + CHUNK]:
            f.write(f"{common.GSI_TILE_URL.replace('{z}/{x}/{y}.pbf', path)}\n  out={path}\n")
print(f"ZL16: 取得済み {have:,} / 未取得 {len(missing):,} タイル {total_bytes / 1e9:.2f} GB → {LISTS} ({(len(missing) + CHUNK - 1) // CHUNK} files)")
