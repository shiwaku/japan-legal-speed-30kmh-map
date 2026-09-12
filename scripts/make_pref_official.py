"""道路統計年報 2024(令和 4 年度末)の都道府県別実延長を data/official/prefectures.json にまとめる。

入力(国土交通省 道路統計年報 2024「道路の現況」、単位 m):
  表15 都道府県別実延長内訳《合計》      d_genkyou15.xlsx  ← 幅員別の内訳もここから取る
  表19 都道府県別実延長内訳〈一般国道〉  d_genkyou19.xlsx
  表22 都道府県別実延長内訳〈都道府県道〉 d_genkyou22.xlsx
  表25 都道府県別実延長内訳（市町村道）  d_genkyou25.xlsx
  高速自動車国道は表16 だが都道府県別の合計行で足りるので、合計 − (国道+都道府県道+市町村道) で出す。
  どの表も都道府県の行に政令指定都市が含まれない(表の合計行 = 都道府県行 + 政令市行)ので、
  政令市の行を親県に足す。足さないと 20 政令市分(表15 で 94,356 km)が抜ける。

    uv run python scripts/make_pref_official.py
"""
import json
import re
from pathlib import Path

import openpyxl

import common

SRC = common.DATA / "official"
OUT = SRC / "prefectures.json"
URL = "https://www.mlit.go.jp/road/ir/ir-data/tokei-nen/2024/nenpo02.html"
PREF_ROW = re.compile(r"^(\d{2})(\d{2})?(\S+)$")  # 「01北海道」(都道府県) と「0110札幌市」(県コード + 市コード)


def read_table(name):
    """'01北海道' の行に、別行になっている政令市('0110札幌市')を足して {code: (県名, [数値...])} で返す。

    都道府県の行には政令指定都市が含まれない(表の合計行 = 都道府県行 + 政令市行)。足さないと
    表25 の市町村道で 84,341 km 抜け、神奈川県は実延長が半分(11,806 → 23,632 km)になる。
    """
    ws = openpyxl.load_workbook(SRC / name, read_only=True, data_only=True).worksheets[0]
    names, vals = {}, {}
    for r in ws.iter_rows(values_only=True):
        if not r or not isinstance(r[0], str):
            continue
        m = PREF_ROW.match(r[0].replace(" ", "").replace("　", ""))
        if not m:
            continue
        code, city, pname = m.groups()
        if city is None:
            if not pname.endswith(("都", "道", "府", "県")):  # 「合計」など都道府県でない行
                continue
            names[code] = pname
        v = [float(x) if isinstance(x, (int, float)) else None for x in r[1:]]
        cur = vals.get(code)
        vals[code] = v if cur is None else [None if a is None and b is None else (a or 0) + (b or 0) for a, b in zip(cur, v)]
    return {c: (names[c], vals[c]) for c in sorted(names)}


def km(v):
    return None if v is None else round(v / 1000, 1)


t15, t19, t22, t25 = (read_table(f"d_genkyou{n}.xlsx") for n in (15, 19, 22, 25))
prefs = {}
for code, (pname, v) in sorted(t15.items()):
    total = v[0]
    # 表15 の列: 実延長計, 改良済 19.5m以上, 13-19.5, 5.5-13, 小計, 未改良 5.5m未満, 計, 5.5m以上, 3.5-5.5, 3.5m未満, 自動車交通不能, 計 ...
    width = {
        "19.5m以上": km(v[1]), "13.0-19.5m": km(v[2]), "5.5-13.0m": km(v[3]),
        "改良済_5.5m未満": km(v[5]), "未改良_5.5m以上": km(v[7]), "未改良_3.5-5.5m": km(v[8]),
        "未改良_3.5m未満": km(v[9]), "うち自動車交通不能": km(v[10]),
    }
    ge55 = sum(x for x in (v[1], v[2], v[3], v[7]) if x)  # 5.5m 以上 = 改良済 3 区分 + 未改良 5.5m以上
    lt55 = sum(x for x in (v[5], v[8], v[9]) if x)          # 5.5m 未満 = 改良済 5.5m未満 + 未改良 3.5-5.5 + 3.5m未満
    kokudo = t19[code][1][0] if code in t19 else None
    todofuken = t22[code][1][0] if code in t22 else None
    shichoson = t25[code][1][0] if code in t25 else None
    kosoku = total - sum(x for x in (kokudo, todofuken, shichoson) if x)
    prefs[code] = {
        "name": pname,
        "official_road_km": {
            "source": f"国土交通省 道路統計年報 2024 道路の現況 表15/19/22/25 {URL}",
            "as_of": "2023-03-31",
            "高速自動車国道等": km(kosoku), "国道": km(kokudo), "都道府県道": km(todofuken), "市区町村道": km(shichoson),
            "合計": km(total),
        },
        "width_km": width,
        "share_lt_5_5m_pct": round(lt55 / total * 100, 1) if total else None,
        "_note": "幅員は道路統計年報 表15(道路法上の道路、実延長)。5.5m 未満の割合は地理院 rnkWidth≤1 の代替指標と比べる目安",
    }

OUT.write_text(json.dumps(prefs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
tot = sum(p["official_road_km"]["合計"] for p in prefs.values())
print(f"{len(prefs)} 都道府県 → {OUT}  全国計 {tot:,.0f} km  (5.5m未満 全国 {sum(p['official_road_km']['合計'] * p['share_lt_5_5m_pct'] / 100 for p in prefs.values()) / tot * 100:.1f}%)")
for c in ("01", "11", "13"):
    p = prefs[c]
    print(c, p["name"], p["official_road_km"], "5.5m未満", p["share_lt_5_5m_pct"], "%")
