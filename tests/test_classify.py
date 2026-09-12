"""判定ロジック(scripts/common.py)の単体テスト。ネットワークもデータも要らない。

    uv run python -m unittest discover -s tests
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import common  # noqa: E402


class ClassifyWidthTest(unittest.TestCase):
    def w(self, **kw):
        base = dict(ftCode=2701, rdCtg=2, rnkWidth=1, medSect=0, motorway=9)
        base.update(kw)
        return common.classify_width(**base)

    def test_typical_residential_road_is_candidate(self):
        self.assertEqual(self.w(), common.CLS_CANDIDATE)
        self.assertEqual(self.w(rnkWidth=0), common.CLS_CANDIDATE)

    def test_motorway_unknown_9_is_not_excluded(self):
        # 実データは 99% が motorway=9(不明)。0 だけ通すと全滅する
        self.assertEqual(self.w(motorway=9), common.CLS_CANDIDATE)
        self.assertEqual(self.w(motorway=0), common.CLS_CANDIDATE)
        self.assertEqual(self.w(motorway=1), common.CLS_MOTORWAY)
        self.assertEqual(self.w(rdCtg=3), common.CLS_MOTORWAY)

    def test_median(self):
        self.assertEqual(self.w(medSect=5), common.CLS_MEDIAN)
        # 99 は「幅員急変等非表示」で分離帯ありではない
        self.assertEqual(self.w(medSect=99), common.CLS_ATTR_UNKNOWN)

    def test_wide_road_is_unknown_not_excluded(self):
        for rw in (2, 3, 4):
            self.assertEqual(self.w(rnkWidth=rw), common.CLS_WIDE_UNKNOWN)

    def test_unknown_width(self):
        self.assertEqual(self.w(rnkWidth=6), common.CLS_ATTR_UNKNOWN)
        self.assertEqual(self.w(rnkWidth=None), common.CLS_ATTR_UNKNOWN)

    def test_minor_roads(self):
        for ft in (2711, 2721, 2731):
            self.assertEqual(self.w(ftCode=ft), common.CLS_MINOR)
        for ft in (2702, 2703, 2704):  # 橋・トンネル等は通常道路
            self.assertEqual(self.w(ftCode=ft), common.CLS_CANDIDATE)


class ClassifyFinalTest(unittest.TestCase):
    def f(self, cls=common.CLS_CANDIDATE, **kw):
        base = dict(frac_speed=0, reg_speed=None, frac_zone=0, zone_speed=None, frac_lane=0, frac_cl=0)
        base.update(kw)
        return common.classify_final(cls, **base)

    def test_no_regulation_candidate_changes(self):
        self.assertEqual(self.f(), common.FINAL_CHANGED)

    def test_speed_sign_wins_when_overlap_high(self):
        self.assertEqual(self.f(frac_speed=0.95, reg_speed="40"), "規制あり:標識40")

    def test_side_street_touching_regulated_road_is_not_regulated(self):
        # 端点だけバッファに入る脇道: 重なり率が低いので規制ありにしない
        self.assertEqual(self.f(frac_speed=0.15, reg_speed="40"), common.FINAL_CHANGED)

    def test_zone30_polygon(self):
        self.assertEqual(self.f(frac_zone=0.8, zone_speed="30"), "規制あり:ゾーン30")
        self.assertEqual(self.f(frac_zone=0.3, zone_speed="30"), common.FINAL_CHANGED)

    def test_faster_sign_beats_area_regulation(self):
        # 兵庫の 40 km/h 区域規制の中にある 80 km/h 標識の幹線を 40 と表示していた(全国 2,296 km)
        self.assertEqual(self.f(frac_zone=0.8, zone_speed="40", frac_speed=0.9, reg_speed="80"), "規制あり:標識80")
        # 標識の方が遅いときは面のまま(ゾーン30 の中の 40 標識の扱いは未決)
        self.assertEqual(self.f(frac_zone=0.8, zone_speed="40", frac_speed=0.9, reg_speed="30"), "規制あり:ゾーン40")
        # 同じ速度、重なりが足りない標識、速度が欠けている規制は面のまま
        self.assertEqual(self.f(frac_zone=0.8, zone_speed="40", frac_speed=0.9, reg_speed="40"), "規制あり:ゾーン40")
        self.assertEqual(self.f(frac_zone=0.8, zone_speed="40", frac_speed=0.3, reg_speed="80"), "規制あり:ゾーン40")
        self.assertEqual(self.f(frac_zone=0.8, zone_speed=None, frac_speed=0.9, reg_speed="80"), "規制あり:ゾーンNone")

    def test_area_regulation_does_not_change_the_60_to_30_verdict(self):
        # 面が勝っても線が勝っても「規制あり」= 変わらないなので、改正前後の速度は標識の値で揃う
        for zone, sign, expect in (("40", "80", "80"), ("40", "30", "40"), ("30", "30", "30")):
            f = self.f(frac_zone=0.8, zone_speed=zone, frac_speed=0.9, reg_speed=sign)
            self.assertEqual(common.speed_before_after(f, sign, zone), (expect, expect))

    def test_lane_and_centerline(self):
        self.assertEqual(self.f(frac_lane=0.9), common.FINAL_LANE)
        self.assertEqual(self.f(frac_cl=0.9), common.FINAL_CENTERLINE)

    def test_wide_unknown_stays_unknown_without_regulation(self):
        self.assertEqual(self.f(cls=common.CLS_WIDE_UNKNOWN), common.CLS_WIDE_UNKNOWN)
        self.assertEqual(self.f(cls=common.CLS_WIDE_UNKNOWN, frac_speed=1.0, reg_speed="50"), "規制あり:標識50")

    def test_excluded_classes_pass_through(self):
        # CLS_MINOR_OLD も含める。言い換える前の 03 の出力に 05 を回し直したとき、軽車道・徒歩道が
        # 素通りして「規制あり」に化けていた(全国 8,900 km)
        for c in (common.CLS_MINOR, common.CLS_MINOR_OLD, common.CLS_MOTORWAY, common.CLS_MEDIAN):
            self.assertEqual(self.f(cls=c, frac_speed=1.0, reg_speed="40"), c)
            self.assertEqual(self.f(cls=c, frac_zone=1.0, zone_speed="30"), c)

    def test_thresholds_are_parameters(self):
        self.assertEqual(common.classify_final(common.CLS_CANDIDATE, 0.6, "40", 0, None, 0, 0, th_line=0.5), "規制あり:標識40")


class SpeedBeforeAfterTest(unittest.TestCase):
    def test_changed_road_60_to_30(self):
        self.assertEqual(common.speed_before_after(common.FINAL_CHANGED, None, None), ("60", "30"))

    def test_signed_road_unchanged(self):
        self.assertEqual(common.speed_before_after("規制あり:標識40", "40", None), ("40", "40"))
        self.assertEqual(common.speed_before_after("規制あり:ゾーン30", None, "30"), ("30", "30"))

    def test_wide_unknown_was_60_now_unknown(self):
        self.assertEqual(common.speed_before_after(common.CLS_WIDE_UNKNOWN, None, None), ("60", common.SPEED_UNKNOWN))

    def test_roads_with_lane_or_median_stay_60(self):
        for f in (common.FINAL_LANE, common.FINAL_CENTERLINE, common.CLS_MEDIAN):
            self.assertEqual(common.speed_before_after(f, None, None), ("60", "60"))

    def test_excluded(self):
        self.assertEqual(common.speed_before_after(common.CLS_MOTORWAY, None, None), (common.SPEED_EXPRESSWAY, common.SPEED_EXPRESSWAY))
        self.assertEqual(common.speed_before_after(common.CLS_MINOR, None, None), (common.SPEED_NA, common.SPEED_NA))


if __name__ == "__main__":
    unittest.main()
