"""国土地理院 最適化ベクトルタイルの標準スタイル(std.json)から、淡色地図風のスタイルを作る。

    uv run python scripts/make_pale_style.py   # → docs/style/pale.json

判定結果の線を主役にしたいので、背景地図は色を抜いて薄くする。std.json を取得し、
paint の色を「白に寄せて彩度を落とす」変換にかける。式(match/case/interpolate)の中の
色文字列も再帰的に置き換える。タイル・スプライト・グリフは地理院のものをそのまま参照する。
"""
import colorsys
import json
import re
from pathlib import Path

import requests

import common

SRC = "https://gsi-cyberjapan.github.io/optimal_bvmap/style/std.json"
DST = common.DOCS / "style" / "pale.json"

HEX = re.compile(r"^#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})$")
RGBA = re.compile(r"^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+)\s*)?\)$")

WATER_WORDS = ("水", "海", "河川", "湖", "池")
BUILDING_WORDS = ("建物", "建築")
GREEN_WORDS = ("植生", "森林", "田", "畑", "公園", "緑")


def parse(c: str):
    if m := HEX.match(c):
        h = m.group(1)
        if len(h) == 3:
            h = "".join(ch * 2 for ch in h)
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)), None
    if m := RGBA.match(c):
        return tuple(int(m.group(i)) for i in (1, 2, 3)), (float(m.group(4)) if m.group(4) else None)
    return None, None


def pale(c: str, to_white: float, sat: float) -> str:
    """白に to_white だけ寄せ、彩度を sat 倍にする。色でなければそのまま返す。"""
    rgb, a = parse(c.strip())
    if rgb is None:
        return c
    h, l, s = colorsys.rgb_to_hls(*(v / 255 for v in rgb))
    l = l + (1 - l) * to_white
    s = s * sat
    r, g, b = (round(v * 255) for v in colorsys.hls_to_rgb(h, l, s))
    return f"rgba({r},{g},{b},{a})" if a is not None else f"#{r:02x}{g:02x}{b:02x}"


def walk(x, fn):
    if isinstance(x, str):
        return fn(x)
    if isinstance(x, list):
        return [walk(v, fn) for v in x]
    if isinstance(x, dict):
        return {k: walk(v, fn) for k, v in x.items()}
    return x


def main():
    style = requests.get(SRC, timeout=60).json()
    for layer in style["layers"]:
        lid = layer["id"]
        paint = layer.setdefault("paint", {})
        t = layer["type"]
        if t == "background":
            paint["background-color"] = "#fbfbfb"
            continue
        # レイヤー名で大まかに色味を決める。細かい分類色は残さない
        if any(w in lid for w in WATER_WORDS):
            to_white, sat = 0.55, 0.6      # 水はうっすら青を残す
        elif any(w in lid for w in GREEN_WORDS):
            to_white, sat = 0.85, 0.3
        elif any(w in lid for w in BUILDING_WORDS):
            to_white, sat = 0.75, 0.0      # 建物は薄いグレー
        elif t == "symbol":
            to_white, sat = 0.25, 0.0      # 注記はグレー文字
        else:
            to_white, sat = 0.65, 0.15     # 道路・境界などはグレー寄り
        for k in list(paint):
            if k.endswith("-color"):
                paint[k] = walk(paint[k], lambda c: pale(c, to_white, sat))
        if t == "symbol":
            paint["text-halo-color"] = "rgba(255,255,255,0.9)"
    # std.json は全国 1 本(17GB)の PMTiles を参照しており、初回表示でディレクトリ取得に 10〜30 秒かかる。
    # 同じタイルが XYZ でも配信されているので、そちらを使う(初回が速い。pmtiles プロトコルも不要)
    for src in style["sources"].values():
        if src.get("type") == "vector":
            src["tiles"] = ["https://cyberjapandata.gsi.go.jp/xyz/optimal_bvmap-v1/{z}/{x}/{y}.pbf"]
            src.pop("url", None)
            src["attribution"] = '<a href="https://github.com/gsi-cyberjapan/optimal_bvmap" target="_blank">国土地理院 最適化ベクトルタイル</a>'
    style["name"] = "GSI optimal_bvmap pale (japan-legal-speed-30kmh-map)"
    style.setdefault("metadata", {})["derived_from"] = SRC
    DST.parent.mkdir(parents=True, exist_ok=True)
    DST.write_text(json.dumps(style, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"{len(style['layers'])} layers → {DST} ({DST.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
