# japan-legal-speed-30kmh-map — この道、60→30？

2026年9月1日施行の改正道路交通法施行令で、**中央線・車両通行帯・中央分離帯のいずれもない一般道路の法定速度が 60 km/h から 30 km/h** に引き下げられました。全国の一般道の約7割が対象とされていますが、どの道路が対象かを示す公式の地図はありません。

このリポジトリは、**国土地理院のベクトルタイル（道路の幅員・分離帯）** と **JARTIC 交通規制情報（速度標識・ゾーン30）** という2つのオープンデータを突き合わせて、「標識が無く法定速度 60 だった道路のうち、中央線等が無いために 30 に変わった道路」を市町村単位で**推定**し、地図で見られるようにするものです。

> **推定であって、確定ではありません。** 中央線そのもののオープンデータは実質存在しないため、幅員 5.5 m 未満を「中央線なし」の代替指標にしています。幅員 5.5 m 以上の道路は中央線の有無を判定できず「不明」と表示します。標識の現地確認に代わるものではありません。

## 地図

<!-- Pages を有効にしたら URL を入れる -->
`docs/index.html`（MapLibre GL JS + PMTiles）。エリアをプルダウンで切り替え、**「判定 / 改正前の速度 / 改正後の速度」**をタブ（または <kbd>B</kbd> キー）で切り替えられます。改正前は標識の無い一般道が一様に 60 km/h（青）で、改正後にその大半が 30 km/h（赤）に変わるのが見えます。凡例のチェックで表示クラスを絞り、道路をクリックすると判定根拠（改正前後の速度・幅員区分・規制の重なり率）が出ます。

![川越市の判定図](out/kawagoe/final.png)

## 判定ロジック

法改正で変わったのは「標識が無く法定速度 60 だった道路のうち、中央線等がないもの」だけです。既存の 30/40/50 標識がある道路は標識の速度が優先され、何も変わりません。

```
① 地理院ベクトルタイル road レイヤー（道路中心線 ftCode 2701–2704）
     rnkWidth ≤ 1（幅員 5.5 m 未満） かつ medSect == 0（分離帯なし）
     かつ motorway != 1 かつ rdCtg != 3（高速等でない）           → 候補
     rnkWidth ∈ {2,3,4}（5.5 m 以上）                              → 不明（中央線有無を判定できない）
② JARTIC 交通規制情報
     最高速度（線, コード 112/61/113）を 10 m バッファ →
       候補線分の長さの 70% 以上がバッファ内                      → 規制あり（標識 XX）
     最高速度（面, コード 114 = ゾーン30）に 50% 以上内包           → 規制あり（ゾーン30）
     車両通行帯（16/17/20/21/118）・中央線（15）も同様に            → 対象外
③ 残った候補                                                        → ★60→30 変更（推定）
```

②を「交差」ではなく**重なり率**で判定するのは、規制のある幹線に接続する脇道が端点だけでバッファに引っかかり、全部「規制あり」に化けてしまうためです。川越市では候補道路の重なり率が「0」か「0.9 以上」に二極化し、曖昧帯（0.3〜0.7）は 3% でした。バッファ幅 5/10/15/20 m で結果は 66→63% と安定しています。

改正前後の速度は `speed_before_after` で付与します（標識・ゾーン30 は前後同じ、変更(推定)は 60→30、幅員 5.5 m 以上は 60→不明(60/30)、分離帯・通行帯ありは 60→60）。判定ロジックは [`scripts/common.py`](scripts/common.py) の `classify_width` / `classify_final` / `speed_before_after` にあり、[`tests/test_classify.py`](tests/test_classify.py) で固定しています。

## 結果

| エリア | 市域内の道路中心線 | ★60→30 変更（推定） | 標識あり | ゾーン30 | 不明（5.5 m 以上） | JARTIC |
|---|---|---|---|---|---|---|
| [川越市](areas/kawagoe.json) | 2,615 km | **1,708 km（65.3%）** | 437 km | 176 km | 47 km（1.8%） | 2026-07 |

詳細は `out/<area>/summary_final.csv`、属性の分布は `out/<area>/summary_attrs.csv`。

## 使い方

```bash
uv sync
uv run python -m unittest discover -s tests

# 1. 市域と交差する地理院ベクトルタイル(ZL16)を列挙  (mokuroku.csv.gz 75MB を初回のみ取得)
uv run python scripts/01_list_tiles.py       --area kawagoe
# 2. タイル取得  (川越: 542 枚 23MB)
uv run python scripts/02_fetch_tiles.py      --area kawagoe
# 3. 道路中心線を取り出して一次判定  (タイル矩形でクリップ→市域でクリップ)
uv run python scripts/03_decode_roads.py     --area kawagoe
# 4. JARTIC 規制を市域で切り出し  (入力は下記の GeoJSONL)
uv run python scripts/04_extract_jartic.py   --area kawagoe --jartic data/jartic/202607
# 5. 重なり率で突合して最終判定。--save で out/<area>/final.* と docs/areas.json を書く
uv run python scripts/05_match_regulation.py --area kawagoe --buffer 10 --save
# 6. PMTiles  (tippecanoe。Windows は WSL2 で)
wsl bash scripts/06_build_pmtiles.sh kawagoe
# 表示  (python -m http.server は Range 非対応で PMTiles を読めない)
uv run python -m RangeHTTPServer 8765 --bind 127.0.0.1   # → http://127.0.0.1:8765/docs/
```

### JARTIC 交通規制情報の用意

配布形式（1 都道府県 1 zip・170 列 CSV・cp932）をそのまま扱うのは大変なので、[jartic-traffic-regulation-converter](https://github.com/shiwaku/jartic-traffic-regulation-converter) でパースした GeoJSONL を入力にします。

```bash
# converter リポジトリで
python3 src/jartic_opendata_kisei_dl.py --out work/zip --only R11      # 埼玉のみ。省略で 47 都道府県 (320MB)
python3 src/parse_regulation.py --zip-dir work/zip --out work
# regulation_speed.geojsonl と regulation_lane.geojsonl を data/jartic/<yyyymm>/ に置く
```

### 新しいエリアを追加する

1. `areas/<key>.json` を作る（`areas/kawagoe.json` を写す）。`epsg` は長さを測る平面直角座標系（例: 札幌 = XII 系 6680）、`boundary_url` は市域 GeoJSON の URL（無ければ `data/areas/<key>/boundary.geojson` を直接置く）
2. 上の 1〜6 を `--area <key>` で回す。`docs/areas.json` にエリアが追記され、ビューワのプルダウンに出る

## ディレクトリ構成

```
areas/<key>.json            エリア定義（名称・EPSG・市域の URL・初期表示位置）
scripts/
  common.py                 パス規約と判定ロジック（ここだけテストされる）
  01_list_tiles.py … 06_build_pmtiles.sh
tests/test_classify.py
data/
  areas/<key>/              boundary.geojson, tiles_z16.csv（コミット）, jartic_*.geojson（04 の出力、ignore）
  gsi/                      mokuroku.csv.gz, tiles/<key>/*.pbf（ignore）
  jartic/<yyyymm>/          converter の GeoJSONL（ignore）
out/<key>/                  roads_z16.parquet, roads_city.geojson, final.{parquet,geojson}（ignore）
                            summary_*.csv, final.png（コミット）
docs/                       GitHub Pages: index.html, areas.json, tiles/<key>.pmtiles
```

## 実データで分かったこと

計画時の想定と違っていた点。他のエリアでも同じ罠を踏まないためのメモ。

- **地理院ベクトルタイルの `motorway` は 99% が 9（不明）**。「`motorway == 0` で一般道に絞る」と全滅する。`== 1` だけを除外する
- **`rnkWidth` の 5（その他）/6（不明）は川越では 0 km**。判定不能率の懸念は都市部では杞憂だった。分布は 3 m 未満 38% / 3〜5.5 m 50% / 5.5〜13 m 10%
- **`Width`（実幅員）は ZL16 タイルに入っていない**。`rnkWidth`（区分）のみ
- road レイヤーには **ftCode 2201（道路縁）が混在**する（件数の約 3 割）。27xx で絞る
- タイルにはバッファが付くので、隣接タイルで同じ道路が二重に入る。延長を出すなら**タイル矩形でクリップ**してから集計する
- **JARTIC の都道府県コードは JIS と異なる**（埼玉 = 12、JIS は 11）。コードでなく空間で絞る
- 埼玉県警は**コード 15「道路の中央線」を提供していない**（16「中央線の変移」のみ）。JARTIC 全国でも 1,048 件・22 都道府県で、中央線の代替には使えない
- **ゾーン30 はコード 114（面）**。線の差分だけでは残るので面内包で除外する（川越で 176 km）
- 2025-07 と 2026-07 の規制データで川越の速度規制は件数・延長ともほぼ同一。施行前の駆け込み標識設置は見られない

## 限界

- 幅員 5.5 m 以上で中央線がない道路（住宅地の 6 m 道路など）は「不明」になる。OSM の `lanes` などで補える可能性はあるが未実装
- 幅員 5.5 m 未満でも中央線が引かれている道路は、原理的に検出できない
- 多車線の一方通行（車両通行帯あり）は 30 にならないが、JARTIC の通行帯データでしか拾えない
- 地理院ベクトルタイルは提供実験中で、URL や属性が変わる可能性がある

## データ出典・ライセンス

- 国土地理院 [ベクトルタイル提供実験](https://github.com/gsi-cyberjapan/gsimaps-vector-experiment)（`experimental_bvmap`、属性仕様は [attribute.pdf](https://maps.gsi.go.jp/help/pdf/vector/attribute.pdf)）— [国土地理院コンテンツ利用規約](https://www.gsi.go.jp/kikakuchousei/kikakuchousei40182.html)
- [JARTIC 交通規制情報](https://www.jartic.or.jp/service/opendata/)（拡張版標準フォーマット k_2.1）— JARTIC オープンデータ利用規約
- 市域: [geoshape.ex.nii.ac.jp 行政区域データ](https://geoshape.ex.nii.ac.jp/city/)（国土数値情報 N03 を元にしたもの）
- ベースマップ: [地理院タイル（淡色地図）](https://maps.gsi.go.jp/development/ichiran.html)

コードは Apache License 2.0（[LICENSE](LICENSE)）。`docs/tiles/*.pmtiles` と `out/` の集計は上記データの派生物で、それぞれの利用規約に従います。
