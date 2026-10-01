// 交通事故(警察庁 交通事故統計オープンデータ 2019〜2024 年、本票 1,895,275 件)。
// npa-traffic-accident-converter/viewer の事故レイヤー(ヒートマップ・点・選択リング・発生日ラベル)と
// フィルタ・ポップアップを移植したもの。PMTiles も converter が R2 に置いたものをそのまま読む。
// 違いは、setStyle(テーマ・背景の切替)で消えるので style.load のたびに addAccidentLayers で貼り直すことと、
// 表示の ON/OFF(既定 OFF)を持つことだけ。
import maplibregl, { type MapMouseEvent } from "maplibre-gl";
import { buildFilter, type FilterState } from "./filters";
import { buildPopupHtml } from "./popup";

const PMTILES_URL = "https://shi-works.com/pmtiles/npa-traffic-accident/honhyo_2019-2024_converted.pmtiles";
const SOURCE_LAYER = "honhyo_20192024_converted";
export const COLOR_FATAL = "#e8003a";
export const COLOR_INJURY = "#2563eb";

const JIKO_LAYERS = ["jiko-heat", "jiko-points", "jiko-labels"] as const;
const ALL_LAYERS = [...JIKO_LAYERS, "jiko-highlight-glow", "jiko-highlight-ring"];

export const filterState: FilterState = {
  naiyou: new Set(["死亡事故", "負傷事故"]),
  years: new Set(["2019", "2020", "2021", "2022", "2023", "2024"]),
  tyuya: new Set(["昼", "夜"]),
  party: "",
  age: "",
};

let enabled = false;
let heatmap = false;
let selected: [number, number] | null = null;

export const accidentsEnabled = (): boolean => enabled;

/** 判定レイヤーと同じ位置(背景の注記の下)に差し込む。選択リングだけは最上位。 */
export function addAccidentLayers(map: maplibregl.Map, before: string | undefined): void {
  for (const id of ALL_LAYERS) if (map.getLayer(id)) map.removeLayer(id);
  for (const id of ["jiko", "selected"]) if (map.getSource(id)) map.removeSource(id);

  map.addSource("jiko", {
    type: "vector",
    url: `pmtiles://${PMTILES_URL}`,
    attribution:
      '<a href="https://www.npa.go.jp/publications/statistics/koutsuu/opendata/index_opendata.html" target="_blank" rel="noopener">警察庁 交通事故統計情報のオープンデータ（2019〜2024年）を加工して作成</a>',
  });
  const add = (layer: Record<string, unknown>, beforeId = before) =>
    map.addLayer(layer as unknown as maplibregl.LayerSpecification, beforeId);

  // ヒートマップ
  add({
    id: "jiko-heat", type: "heatmap", source: "jiko", "source-layer": SOURCE_LAYER,
    paint: {
      "heatmap-weight": 1,
      // 高ズームほど実ポイント数が増える(タイル間引きが減る)ため、強度は逆に下げる
      "heatmap-intensity": ["interpolate", ["linear"], ["zoom"], 4, 1.4, 6, 1.0, 8, 0.5, 10, 0.22, 12, 0.1, 14, 0.06],
      "heatmap-radius": ["interpolate", ["linear"], ["zoom"], 4, 2.5, 9, 7, 14, 14],
      "heatmap-color": [
        "interpolate", ["linear"], ["heatmap-density"],
        0, "rgba(33, 102, 172, 0)",
        0.15, "rgba(43, 131, 226, 0.7)",
        0.35, "rgba(0, 180, 200, 0.78)",
        0.55, "rgba(90, 200, 70, 0.82)",
        0.75, "rgba(250, 205, 40, 0.88)",
        0.9, "rgba(245, 140, 30, 0.92)",
        1, "rgba(226, 20, 45, 0.95)",
      ],
      "heatmap-opacity": 0.88,
    },
  });
  // 事故ポイント(死亡=赤 / 負傷=青、死亡を上に描画)
  add({
    id: "jiko-points", type: "circle", source: "jiko", "source-layer": SOURCE_LAYER,
    layout: { "circle-sort-key": ["match", ["get", "事故内容"], "死亡事故", 1, 0] },
    paint: {
      "circle-color": ["match", ["get", "事故内容"], "死亡事故", COLOR_FATAL, COLOR_INJURY],
      "circle-radius": ["interpolate", ["linear"], ["zoom"], 4, 1.4, 8, 2.6, 12, 5, 16, 8],
      "circle-opacity": 0.85,
      "circle-stroke-color": "#ffffff",
      "circle-stroke-width": ["interpolate", ["linear"], ["zoom"], 4, 0.2, 12, 1.2],
      "circle-stroke-opacity": 0.9,
    },
  });
  // 発生日ラベル(高ズームのみ)
  add({
    id: "jiko-labels", type: "symbol", source: "jiko", "source-layer": SOURCE_LAYER, minzoom: 16,
    layout: {
      "text-field": ["concat", ["get", "発生日時_年"], "/", ["get", "発生日時_月"], "/", ["get", "発生日時_日"]],
      "text-font": ["NotoSansJP-Regular"],
      "text-offset": [0, -1.3],
      "text-allow-overlap": true,
      "text-size": 12,
    },
    paint: {
      "text-color": ["match", ["get", "事故内容"], "死亡事故", COLOR_FATAL, COLOR_INJURY],
      "text-halo-color": "#ffffff",
      "text-halo-width": 1,
    },
  });
  // 選択中の事故ポイントのハイライト
  map.addSource("selected", { type: "geojson", data: fc(selected) });
  add({
    id: "jiko-highlight-glow", type: "circle", source: "selected",
    paint: { "circle-color": "#ffab00", "circle-opacity": 0.25, "circle-radius": ["interpolate", ["linear"], ["zoom"], 4, 10, 8, 14, 12, 18, 16, 24] },
  }, undefined);
  add({
    id: "jiko-highlight-ring", type: "circle", source: "selected",
    paint: {
      "circle-color": "rgba(0, 0, 0, 0)",
      "circle-radius": ["interpolate", ["linear"], ["zoom"], 4, 6, 8, 9, 12, 12, 16, 16],
      "circle-stroke-color": "#ff9500",
      "circle-stroke-width": 3,
    },
  }, undefined);
  applyAccidents(map);
}

const fc = (coords: [number, number] | null): GeoJSON.FeatureCollection => ({
  type: "FeatureCollection",
  features: coords ? [{ type: "Feature", geometry: { type: "Point", coordinates: coords }, properties: {} }] : [],
});

function applyAccidents(map: maplibregl.Map): void {
  if (!map.getLayer("jiko-points")) return;
  const filter = buildFilter(filterState);
  for (const id of JIKO_LAYERS) map.setFilter(id, filter);
  const vis = (on: boolean) => (on ? "visible" : "none");
  map.setLayoutProperty("jiko-heat", "visibility", vis(enabled && heatmap));
  map.setLayoutProperty("jiko-points", "visibility", vis(enabled && !heatmap));
  map.setLayoutProperty("jiko-labels", "visibility", vis(enabled && !heatmap));
}

/** 点の下に事故があるか。判定線のポップアップと重ならないよう、main 側のクリック処理が使う。 */
export const hitAccident = (map: maplibregl.Map, point: maplibregl.PointLike): boolean =>
  !!map.getLayer("jiko-points") && map.queryRenderedFeatures(point, { layers: ["jiko-points"] }).length > 0;

/** パネル UI・クリック・件数表示。onToggle は URL の同期用。 */
export function initAccidents(map: maplibregl.Map, initial: boolean, onToggle: () => void): void {
  enabled = initial;
  const opts = document.getElementById("acc-opts") as HTMLElement;
  const toggle = document.getElementById("acc-toggle") as HTMLInputElement;
  toggle.checked = enabled;
  opts.hidden = !enabled;
  toggle.addEventListener("change", () => {
    enabled = toggle.checked;
    opts.hidden = !enabled;
    if (!enabled) clearSelection();
    applyAccidents(map);
    onToggle();
  });

  // ---- 選択ハイライトとポップアップ ----
  // クリックごとにポップアップを新規生成する(使い回すと addTo() が内部で remove() を呼んで close が発火し、
  // 直前に設定したハイライトを消してしまう)。前のポップアップは close リスナを外してから remove する。
  let selectedPopup: maplibregl.Popup | null = null;
  const setHighlight = (coords: [number, number] | null): void => {
    selected = coords;
    (map.getSource("selected") as maplibregl.GeoJSONSource | undefined)?.setData(fc(coords));
  };
  const onPopupClose = (): void => { selectedPopup = null; setHighlight(null); };
  const removeSelectedPopup = (): void => {
    if (!selectedPopup) return;
    const p = selectedPopup;
    selectedPopup = null;
    p.off("close", onPopupClose);
    p.remove();
  };
  const clearSelection = (): void => { removeSelectedPopup(); setHighlight(null); };

  map.on("click", "jiko-points", (e: MapMouseEvent & { features?: maplibregl.MapGeoJSONFeature[] }) => {
    const feature = e.features?.[0];
    if (!feature) return;
    const [lng, lat] = (feature.geometry as GeoJSON.Point).coordinates;
    removeSelectedPopup();
    setHighlight([lng, lat]);
    // focusAfterOpen を切らないと、最初のリンク(本文末尾の Google Maps)にフォーカスが移って本文が最下部までスクロールする
    selectedPopup = new maplibregl.Popup({ maxWidth: "360px", closeOnClick: false, focusAfterOpen: false, className: "acc-pop" })
      .setLngLat([lng, lat])
      .setHTML(buildPopupHtml(feature.properties as Record<string, unknown>, lng, lat))
      .addTo(map);
    selectedPopup.on("close", onPopupClose);
  });
  // 事故ポイント以外をクリックしたら選択を解除する(レイヤ用ハンドラとの実行順に依存しない)
  map.on("click", (e) => { if (!hitAccident(map, e.point)) clearSelection(); });
  if (window.matchMedia("(hover: hover)").matches) {
    map.on("mouseenter", "jiko-points", () => { map.getCanvas().style.cursor = "pointer"; });
    map.on("mouseleave", "jiko-points", () => { map.getCanvas().style.cursor = ""; });
  }

  // ---- フィルタ ----
  const setupChipGroup = (containerId: string, values: Set<string>): void => {
    document.getElementById(containerId)!.querySelectorAll<HTMLButtonElement>(".chip").forEach((chip) => {
      chip.addEventListener("click", () => {
        const value = chip.dataset.value!;
        if (values.has(value)) { values.delete(value); chip.classList.remove("active"); }
        else { values.add(value); chip.classList.add("active"); }
        applyAccidents(map);
      });
    });
  };
  setupChipGroup("acc-naiyou", filterState.naiyou);
  setupChipGroup("acc-year", filterState.years);
  setupChipGroup("acc-tyuya", filterState.tyuya);
  document.getElementById("acc-party")!.addEventListener("change", (e) => {
    filterState.party = (e.target as HTMLSelectElement).value;
    applyAccidents(map);
  });
  document.getElementById("acc-age")!.addEventListener("change", (e) => {
    filterState.age = (e.target as HTMLSelectElement).value;
    applyAccidents(map);
  });

  // 表示モード(ポイント / ヒートマップ)
  const modeBtns = document.querySelectorAll<HTMLButtonElement>("#acc-mode button");
  modeBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      heatmap = btn.dataset.value === "heatmap";
      modeBtns.forEach((b) => b.setAttribute("aria-selected", String(b === btn)));
      applyAccidents(map);
    });
  });

  // 画面内の描画済み件数(タイル間引きがあるため目安)
  const statsEl = document.getElementById("acc-stats")!;
  map.on("idle", () => {
    if (!enabled || !map.getLayer("jiko-points")) return;
    if (heatmap) { statsEl.textContent = "ヒートマップ表示中"; return; }
    const seen = new Set<string>();
    for (const f of map.queryRenderedFeatures({ layers: ["jiko-points"] })) {
      const p = f.properties as Record<string, unknown>;
      seen.add(`${p["都道府県名"]}|${p["発生日時_年"]}|${p["本票番号"]}`);
    }
    statsEl.textContent = `画面内: ${seen.size.toLocaleString()} 件（描画済みポイント・目安）`;
  });
  // style.load が先に走っていればレイヤーは既定(非表示)で載っているので、初期状態を反映する
  applyAccidents(map);
}
