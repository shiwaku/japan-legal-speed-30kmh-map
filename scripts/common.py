"""各スクリプト共通: エリア定義の読み込み・パス規約・判定ロジック。

エリアは areas/<key>.json に定義する。パスは全てリポジトリルート基準なので、
どのディレクトリから実行してもよい。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AREAS = ROOT / "areas"
DATA = ROOT / "data"
OUT = ROOT / "out"
DOCS = ROOT / "viewer" / "public"  # ビューワ(Vite)の静的ファイル置き場。areas.json, tiles/, pale.json

GSI_TILE_URL = "https://cyberjapandata.gsi.go.jp/xyz/experimental_bvmap/{z}/{x}/{y}.pbf"
GSI_MOKUROKU_URL = "https://cyberjapandata.gsi.go.jp/xyz/experimental_bvmap/mokuroku.csv.gz"
GSI_ZOOM = 16  # ZL17 相当のデータは ZL16 に含まれる(overzoom)ので、ZL16 で網羅できる


class Area:
    """areas/<key>.json とそこから決まるパス。"""

    def __init__(self, key: str):
        p = AREAS / f"{key}.json"
        if not p.exists():
            raise SystemExit(f"{p} が無い。areas/kawagoe.json を写して作る")
        cfg = json.loads(p.read_text(encoding="utf-8"))
        self.key = key
        self.name: str = cfg["name"]
        self.epsg: int = cfg["epsg"]  # 平面直角座標系。長さ・バッファはこの CRS で測る
        self.boundary_url: str | None = cfg.get("boundary_url")
        self.view: dict = cfg.get("view", {})
        self.cfg = cfg

        self.data = DATA / "areas" / key
        self.boundary = self.data / "boundary.geojson"
        self.tiles_csv = self.data / "tiles_z16.csv"
        self.jartic_lines = self.data / "jartic_lines.geojson"
        self.jartic_polygons = self.data / "jartic_polygons.geojson"
        self.tiles_dir = DATA / "gsi" / "tiles" / key
        self.out = OUT / key
        self.pmtiles = DOCS / "tiles" / f"{key}.pmtiles"

        for d in (self.data, self.tiles_dir, self.out):
            d.mkdir(parents=True, exist_ok=True)

    def geometry(self):
        """市域ポリゴン(EPSG:4326, shapely)。無ければ boundary_url から取る。"""
        import geopandas as gpd

        if not self.boundary.exists():
            if not self.boundary_url:
                raise SystemExit(f"{self.boundary} が無く boundary_url も未設定")
            import requests

            r = requests.get(self.boundary_url, timeout=60)
            r.raise_for_status()
            self.boundary.write_bytes(r.content)
            print(f"市域を取得: {self.boundary_url}")
        return gpd.read_file(self.boundary).union_all()


def parser(description: str) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=description)
    p.add_argument("--area", required=True, help="areas/<key>.json の key (例: kawagoe)")
    return p


# ---- 判定 -------------------------------------------------------------------
# 改正道路交通法施行令(2026-09-01): 中央線・車両通行帯・中央分離帯のいずれもない
# 一般道路の法定速度が 60 → 30 km/h。標識で指定された道路は指定速度が優先。

CLS_CANDIDATE = "候補:幅員5.5m未満・分離帯なし"
CLS_WIDE_UNKNOWN = "不明:幅員5.5m以上(中央線有無不明)"
CLS_ATTR_UNKNOWN = "不明:属性不明"
CLS_MEDIAN = "対象外:分離帯あり"
CLS_MOTORWAY = "対象外:高速等"
CLS_MINOR = "非車道(軽車道・徒歩道等を除く)(ftCode)"

FINAL_CHANGED = "★60→30 変更(推定)"
FINAL_LANE = "対象外:車両通行帯あり"
FINAL_CENTERLINE = "対象外:中央線(JARTIC)"

# 表示順と色。ビューワ(viewer/src/classes.ts)と図(05)が共有する。
FINAL_STYLE = [
    (FINAL_CHANGED, "#d62728"),
    (CLS_WIDE_UNKNOWN, "#ff9f1c"),
    ("規制あり:標識30", "#9ecae1"),
    ("規制あり:標識40", "#4292c6"),
    ("規制あり:標識50", "#08519c"),
    ("規制あり:標識60", "#08306b"),
    ("規制あり:標識80", "#08306b"),
    ("規制あり:ゾーン30", "#74c476"),
    (FINAL_LANE, "#756bb1"),
    (FINAL_CENTERLINE, "#54278f"),
    (CLS_MEDIAN, "#636363"),
    (CLS_MOTORWAY, "#000000"),
    (CLS_ATTR_UNKNOWN, "#e377c2"),
    (CLS_MINOR, "#bdbdbd"),
]


def classify_width(ftCode: int, rdCtg, rnkWidth, medSect, motorway) -> str:
    """地理院ベクトルタイル road レイヤーの属性だけで決まる一次判定。

    属性値は attribute.pdf(令和7年11月21日版) に従う:
      rnkWidth 0:3m未満 1:3-5.5m 2:5.5-13m 3:13-19.5m 4:19.5m以上 5:その他 6:不明
      medSect  0:分離帯無し 1-98:分離帯幅(m) 99:幅員急変等非表示
      motorway 0:高速以外 1:高速 9:不明   ← 実データは 99% が 9 なので「1 のみ除外」
      rdCtg    3:高速自動車国道等
    """
    if not 2701 <= ftCode <= 2704:  # 軽車道(271x)・徒歩道(272x)・庭園路(273x)など
        return CLS_MINOR
    if motorway == 1 or rdCtg == 3:
        return CLS_MOTORWAY
    if medSect not in (0, 99, None):
        return CLS_MEDIAN
    if rnkWidth in (2, 3, 4):  # 5.5m 以上: 中央線の有無を公開データから決められない
        return CLS_WIDE_UNKNOWN
    if rnkWidth in (5, 6, None) or medSect in (99, None):
        return CLS_ATTR_UNKNOWN
    return CLS_CANDIDATE


def classify_final(
    cls: str,
    frac_speed: float,
    reg_speed,
    frac_zone: float,
    zone_speed,
    frac_lane: float,
    frac_cl: float,
    th_line: float = 0.7,
    th_poly: float = 0.5,
) -> str:
    """一次判定に JARTIC 規制の重なり率を重ねた最終判定。

    frac_* は「GSI 線分の長さのうち、規制線のバッファ(or 面規制)に入る比率」。
    交差点で接する脇道が端点だけで引っかからないよう、交差ではなく比率で見る。
    """
    if cls in (CLS_MINOR, CLS_MOTORWAY, CLS_MEDIAN):
        return cls
    if frac_zone >= th_poly:
        return f"規制あり:ゾーン{zone_speed}"
    if frac_speed >= th_line:
        return f"規制あり:標識{reg_speed}"
    if frac_lane >= th_line:
        return FINAL_LANE
    if frac_cl >= th_line:
        return FINAL_CENTERLINE
    if cls == CLS_CANDIDATE:
        return FINAL_CHANGED
    return cls  # 不明:幅員5.5m以上 / 不明:属性不明


SPEED_UNKNOWN = "不明(60/30)"
SPEED_EXPRESSWAY = "高速"
SPEED_NA = "対象外"

# 改正前後の速度の表示順と色。ビューワ(viewer/src/classes.ts)の SPEED_STYLE と同じ
SPEED_STYLE = [
    ("20", "#7f0000"),
    ("30", "#d62728"),
    ("40", "#ff7f0e"),
    ("50", "#2ca02c"),
    ("60", "#1f77b4"),
    ("80", "#08306b"),
    ("100", "#08306b"),
    (SPEED_UNKNOWN, "#ff9f1c"),
    (SPEED_EXPRESSWAY, "#000000"),
    (SPEED_NA, "#bdbdbd"),
]


def speed_before_after(final: str, reg_speed, zone_speed) -> tuple[str, str]:
    """最終判定から、改正前(2026-08-31 まで)と改正後の(推定)最高速度を文字列で返す。

    標識・ゾーン30 のある道路は改正の前後で変わらない。標識の無い一般道は
    改正前は法定 60。改正後は中央線等の有無で 30 か 60 に分かれ、幅員 5.5m 以上で
    判定できないものは「不明(60/30)」。
    """
    if final.startswith("規制あり:ゾーン"):
        s = str(zone_speed or "30")
        return s, s
    if final.startswith("規制あり:標識"):
        s = str(reg_speed)
        return s, s
    if final == FINAL_CHANGED:
        return "60", "30"
    if final in (CLS_WIDE_UNKNOWN, CLS_ATTR_UNKNOWN):
        return "60", SPEED_UNKNOWN
    if final in (FINAL_LANE, FINAL_CENTERLINE, CLS_MEDIAN):
        return "60", "60"
    if final == CLS_MOTORWAY:
        return SPEED_EXPRESSWAY, SPEED_EXPRESSWAY
    return SPEED_NA, SPEED_NA  # 軽車道・徒歩道など、判定対象から外したもの
