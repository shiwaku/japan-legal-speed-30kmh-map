"""全国版: 47 都道府県を順に 03'(GDAL でタイルディレクトリから抽出) → 04 → 05 --save で回す。

    uv run python scripts/run_prefectures.py                 # 全県。済んだ県(out/pref_XX/final.parquet あり)は飛ばす
    uv run python scripts/run_prefectures.py 11 13 --force   # 指定県をやり直す

ログは out/pref_XX/pipeline.log。途中で落ちても次の県に進み、最後に失敗した県を並べる。
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

import common

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("codes", nargs="*", help="都道府県コード(01–47)。省略で全県")
p.add_argument("--force", action="store_true", help="final.parquet があってもやり直す")
p.add_argument("--jartic", default="data/jartic/202607")
p.add_argument("--buffer", default="10")
args = p.parse_args()

codes = args.codes or [f"{i:02d}" for i in range(1, 48)]
if not all((common.AREAS / f"pref_{c}.json").exists() for c in codes):
    print("エリア定義を生成: make_pref_areas.py")
    subprocess.run([sys.executable, str(common.ROOT / "scripts" / "make_pref_areas.py"), *codes], check=True)

failed = []
t0 = time.time()
for c in codes:
    key = f"pref_{c}"
    out = common.OUT / key
    out.mkdir(parents=True, exist_ok=True)
    if not args.force and (out / "final.parquet").exists():
        print(f"{key}: 済み"); continue
    log = open(out / "pipeline.log", "a", encoding="utf-8")
    t1 = time.time()
    ok = True
    for step in (
        ["scripts/03_extract_roads_gdal.py", "--area", key],
        ["scripts/04_extract_jartic.py", "--area", key, "--jartic", args.jartic],
        ["scripts/05_match_regulation.py", "--area", key, "--buffer", args.buffer, "--save"],
    ):
        log.write(f"\n[{Path(step[0]).stem} start] {time.strftime('%H:%M:%S')}\n"); log.flush()
        r = subprocess.run([sys.executable, str(common.ROOT / step[0]), *step[1:]], stdout=log, stderr=subprocess.STDOUT, cwd=common.ROOT)
        if r.returncode != 0:
            ok = False
            log.write(f"[{Path(step[0]).stem} FAILED rc={r.returncode}]\n")
            break
    log.close()
    print(f"{key}: {'OK' if ok else 'FAILED'} {time.time() - t1:,.0f}s  (累計 {(time.time() - t0) / 60:,.0f} 分)", flush=True)
    if not ok:
        failed.append(key)
print("失敗:", failed or "なし")
