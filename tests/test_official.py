"""data/official/prefectures.json が道路統計年報の合計と一致するか。

道路統計年報の都道府県の行には政令指定都市が含まれず、表の合計行 = 都道府県行 + 政令市行 になっている。
都道府県の行だけを読むと 20 政令市分(表15 で 94,356 km、神奈川の市町村道は半分)が抜け、
「道路法上の道路に換算した割合」の下限が実際より低く出る。合計行と突き合わせて取りこぼしを検出する。
"""
import json
import unittest
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[1]
OFFICIAL = ROOT / "data" / "official"
# 表 → prefectures.json の official_road_km のキー
TABLES = {15: "合計", 19: "国道", 22: "都道府県道", 25: "市区町村道"}


def total_row_km(table: int) -> float:
    """表の「合  計」行の実延長計(m)を km で返す。"""
    ws = openpyxl.load_workbook(OFFICIAL / f"d_genkyou{table}.xlsx", read_only=True, data_only=True).worksheets[0]
    for r in ws.iter_rows(values_only=True):
        if r and isinstance(r[0], str) and "合計" in r[0].replace(" ", "").replace("　", "") and isinstance(r[1], (int, float)):
            return r[1] / 1000
    raise AssertionError(f"表{table} に合計行が無い")


class OfficialTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prefs = json.loads((OFFICIAL / "prefectures.json").read_text(encoding="utf-8"))

    def test_47_prefectures(self):
        self.assertEqual(len(self.prefs), 47)

    def test_totals_match_the_yearbook(self):
        for table, key in TABLES.items():
            with self.subTest(table=table, key=key):
                got = sum(p["official_road_km"][key] for p in self.prefs.values())
                # 端数は 1 県あたり 0.05 km までの丸め誤差(47 県で 2.35 km)
                self.assertAlmostEqual(got, total_row_km(table), delta=2.5,
                                       msg=f"表{table} の合計と合わない。政令市の行を足し忘れていないか")

    def test_breakdown_sums_to_total(self):
        for code, p in self.prefs.items():
            with self.subTest(pref=code):
                o = p["official_road_km"]
                parts = sum(o[k] for k in ("高速自動車国道等", "国道", "都道府県道", "市区町村道"))
                self.assertAlmostEqual(parts, o["合計"], delta=0.5)

    def test_width_share(self):
        for code, p in self.prefs.items():
            with self.subTest(pref=code):
                self.assertGreater(p["share_lt_5_5m_pct"], 0)
                self.assertLess(p["share_lt_5_5m_pct"], 100)


if __name__ == "__main__":
    unittest.main()
