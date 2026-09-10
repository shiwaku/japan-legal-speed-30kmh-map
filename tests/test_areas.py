"""areas/*.json の必須項目。特に道路統計(official_road_km)は全エリアで必須。

地理院の中心線は私道・農道など道路法適用外の道路も含むため、道路統計の実延長と
比べずに割合を出すと、報道の「全国の約 7 割」(道路法上の道路が分母)と比較できない。
"""
import json
import unittest
from pathlib import Path

AREAS = sorted((Path(__file__).resolve().parents[1] / "areas").glob("*.json"))


class AreasTest(unittest.TestCase):
    def test_at_least_one_area(self):
        self.assertTrue(AREAS)

    def test_required_keys(self):
        for p in AREAS:
            with self.subTest(area=p.name):
                a = json.loads(p.read_text(encoding="utf-8"))
                for k in ("name", "epsg", "view"):
                    self.assertIn(k, a)
                self.assertIsInstance(a["epsg"], int)
                self.assertEqual(len(a["view"]["center"]), 2)

    def test_official_road_km_is_required(self):
        for p in AREAS:
            with self.subTest(area=p.name):
                a = json.loads(p.read_text(encoding="utf-8"))
                self.assertIn("official_road_km", a, "道路統計の実延長が無い")
                o = a["official_road_km"]
                for k in ("source", "as_of", "国道", "都道府県道", "市区町村道"):
                    self.assertIn(k, o)
                for k in ("国道", "都道府県道", "市区町村道"):
                    self.assertGreater(o[k], 0)
                self.assertTrue(o["source"].startswith(("http", "https")) or " http" in o["source"], "出典 URL を書く")


if __name__ == "__main__":
    unittest.main()
