import maplibregl from "maplibre-gl";
import { Protocol } from "pmtiles";
import "maplibre-gl/dist/maplibre-gl.css";

import { BASEMAPS, getBasemapStyle, insertBeforeId, type Basemap } from "./basemap";
import { CHANGED, CTG, MODES, MUNI_STEPS, WIDTH, defaultOff, label, orderedClasses, type AreaInfo, type Mode, type MuniInfo } from "./classes";
import { applyThemeAttr, initialTheme, type Theme } from "./theme";
import "./style.css";

let theme: Theme = initialTheme();
let base: Basemap = "pale";
let mode: Mode = "final";
applyThemeAttr(theme);

const isMobile = window.matchMedia("(max-width: 640px)").matches;
const BASE_URL = import.meta.env.BASE_URL;

const protocol = new Protocol();
maplibregl.addProtocol("pmtiles", protocol.tile);

// ---- エリア定義(public/areas.json。scripts/05 と make_national_summary が書く) ----
const areas: Record<string, AreaInfo> = await (await fetch(`${BASE_URL}areas.json`)).json();
const params = new URLSearchParams(location.search);
// Map を作ると hash:true が即座に #z/lat/lng を書くので、URL にハッシュがあったかは先に見ておく
const initialNoHash = location.hash.length <= 1;
const firstKey = Object.keys(areas)[0];
let current = params.get("area") && areas[params.get("area")!] ? params.get("area")! : firstKey;
const kindOf = (a: AreaInfo): "japan" | "prefecture" | "city" => a.kind ?? "city";
/** 都道府県・全国は外部の全国 PMTiles を共有。市区町村は public/tiles/<key>.pmtiles */
const tilesUrl = (key: string, a: AreaInfo): string =>
  a.tiles ? a.tiles : `${location.origin}${BASE_URL}tiles/${key}.pmtiles?v=${encodeURIComponent(a.generated)}`;
// 作り直したときに古い Range キャッシュと混ざらないよう、ビルド時刻を付ける
const MUNI_TILES = `${location.origin}${BASE_URL}tiles/municipalities.pmtiles?v=${encodeURIComponent(__BUILD_TIME__)}`;

// 非表示にしている区分(モードごと)。既定は classes.ts の on / defaultOff。
// タイルに新しい区分名が現れても凡例に出せるよう、「出したもの」ではなく「隠したもの」を持つ
const off: Record<Mode, Set<string>> = { final: new Set(), speed_before: new Set(), speed_after: new Set() };
const seen: Record<Mode, Set<string>> = { final: new Set(), speed_before: new Set(), speed_after: new Set() };
function ensureDefaults(m: Mode, values: string[]): void {
  for (const v of values) {
    if (seen[m].has(v)) continue;
    seen[m].add(v);
    if (defaultOff(m, v)) off[m].add(v);
  }
}

// ---- 地図 ----
const view = areas[current].view;
const map = new maplibregl.Map({
  container: "map",
  style: await getBasemapStyle(base, theme),
  center: view.center,
  zoom: view.zoom,
  minZoom: 4,
  maxZoom: 18,
  hash: true,
  attributionControl: false,
  // モバイルは GPU/メモリが限られるので保持タイル数と描画解像度を絞る(WebGL コンテキスト消失の予防)
  maxTileCacheSize: isMobile ? 24 : undefined,
  pixelRatio: isMobile ? Math.min(window.devicePixelRatio || 1, 2) : undefined,
});
map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
map.addControl(
  new maplibregl.GeolocateControl({ positionOptions: { enableHighAccuracy: false }, fitBoundsOptions: { maxZoom: 16 }, trackUserLocation: true }),
  "top-right",
);
map.addControl(new maplibregl.ScaleControl({ maxWidth: 160, unit: "metric" }), "bottom-left");
map.addControl(new maplibregl.AttributionControl({ compact: true }));

// ---- 判定レイヤー ----
// zoom の interpolate は 1 式に 1 つしか置けないので、太さの分岐は各ストップの中で行う
const w = (z10: unknown, z14: unknown, z17: unknown) => ["interpolate", ["linear"], ["zoom"], 10, z10, 14, z14, 17, z17];
const emphasized = () =>
  mode === "final" ? ["==", ["get", "final"], CHANGED] : ["in", ["get", mode], ["literal", ["20", "30"]]];
/** 車道以外(区分名が (ftCode) で終わる)と速度モードの「対象外」は薄く引く */
const dimmed = () =>
  mode === "final" ? ["in", "(ftCode)", ["to-string", ["get", "final"]]] : ["==", ["get", mode], "対象外"];
const paint = () => {
  const st = MODES.find((m) => m.key === mode)!.style;
  return {
    "line-color": ["match", ["get", mode], ...st.flatMap((s) => [s.value, s.color]), "#999"],
    "line-width": w(["case", emphasized(), 0.8, 1.0], ["case", emphasized(), 2.2, 2.4], 6),
    "line-opacity": ["case", dimmed(), 0.5, 0.95],
  } as Record<string, unknown>;
};

/** 市区町村の面塗り(変更率 %)。ズーム 12 未満だけ。 */
const muniFillColor = () => ["step", ["get", "pct"], MUNI_STEPS[0][1], ...MUNI_STEPS.slice(1).flatMap(([v, c]) => [v, c])];
const MUNI_ONLY = ["all", ["!=", ["get", "lv"], 2], ["has", "pct"]]; // 政令市全体は区と重なるので外す

// setStyle 直後はスタイル読込中で addSource が例外になる。読込完了は style.load 側で拾って載せ直す
let styleReady = false;
map.on("style.load", () => { styleReady = true; addDataLayers(); });

const OUR_LAYERS = ["muni-fill", "roads-casing", "roads", "muni-border", "muni-outline", "muni-label"];

function addDataLayers(): void {
  if (!styleReady) return;
  for (const id of OUR_LAYERS) if (map.getLayer(id)) map.removeLayer(id);
  for (const id of ["roads", "muni"]) if (map.getSource(id)) map.removeSource(id);

  const a = areas[current];
  map.addSource("roads", {
    type: "vector", url: `pmtiles://${tilesUrl(current, a)}`,
    attribution: '<a href="https://github.com/gsi-cyberjapan/gsimaps-vector-experiment" target="_blank" rel="noopener">国土地理院 ベクトルタイル提供実験</a> / <a href="https://www.jartic.or.jp/service/opendata/" target="_blank" rel="noopener">JARTIC 交通規制情報</a>',
  });
  map.addSource("muni", {
    type: "vector", url: `pmtiles://${MUNI_TILES}`,
    attribution: '<a href="https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-N03-2024.html" target="_blank" rel="noopener">国土数値情報 行政区域</a>',
  });
  // 背景地図の注記より下、建物・道路より上に差し込む(写真・白図では最上位)
  const before = insertBeforeId(map.getStyle());
  const add = (layer: Record<string, unknown>) => map.addLayer(layer as unknown as maplibregl.LayerSpecification, before);

  // 広域(ズーム 12 未満)は市区町村ごとの変更率を面で。判定線が出てくると入れ替わる
  add({
    id: "muni-fill", type: "fill", source: "muni", "source-layer": "muni", maxzoom: 12, filter: MUNI_ONLY,
    paint: { "fill-color": muniFillColor(), "fill-opacity": ["interpolate", ["linear"], ["zoom"], 4, 0.78, 11.5, 0.78, 12, 0.4] },
  });
  add({
    id: "roads-casing", type: "line", source: "roads", "source-layer": "roads",
    paint: { "line-color": "#fff", "line-width": w(1.2, 3.5, 9), "line-opacity": 0.7 },
  });
  add({
    id: "roads", type: "line", source: "roads", "source-layer": "roads",
    layout: { "line-cap": "round", "line-join": "round" }, paint: paint(),
  });
  // 行政区域(国土数値情報 N03)の境界線と、選択中の市区町村の輪郭
  add({
    id: "muni-border", type: "line", source: "muni", "source-layer": "muni", filter: ["!=", ["get", "lv"], 2],
    layout: { "line-join": "round" },
    paint: {
      "line-color": "#111",
      "line-width": ["interpolate", ["linear"], ["zoom"], 5, 0.5, 10, 0.8, 14, 1.2, 17, 2],
      // 広域では面塗りの邪魔になるので薄く
      "line-opacity": ["interpolate", ["linear"], ["zoom"], 5, 0.35, 9, 0.5, 12, 0.6],
    },
  });
  add({
    id: "muni-outline", type: "line", source: "muni", "source-layer": "muni", filter: ["==", ["get", "code"], ""],
    layout: { "line-join": "round" }, paint: { "line-color": "#111", "line-width": w(2, 3, 5), "line-dasharray": [2, 1.5], "line-opacity": 0.95 },
  });
  // 変更率のラベル(代表点)。市区町村名の注記と同じ場所に出るので、衝突判定を外して少し下にずらす
  map.addLayer({
    id: "muni-label", type: "symbol", source: "muni", "source-layer": "muni_pt", minzoom: 9, maxzoom: 12, filter: MUNI_ONLY,
    layout: {
      "text-field": ["concat", ["to-string", ["round", ["get", "pct"]]], "%"],
      "text-font": ["NotoSansJP-Regular"],
      "text-size": ["interpolate", ["linear"], ["zoom"], 9, 11, 11, 13],
      "text-offset": [0, 1.2],
      "text-allow-overlap": true,
      "text-ignore-placement": true,
    },
    paint: {
      "text-color": "#1a1a1a",
      "text-halo-color": "rgba(255,255,255,0.9)",
      "text-halo-width": 1.4,
      // Z9 では車道 1,000 km 超の市区町村だけ(数が多いと読めない)。Z10 以上は全部。
      // zoom 式は 1 つの interpolate にしか置けないので、各ストップの中で分岐する
      "text-opacity": ["interpolate", ["linear"], ["zoom"], 9, ["case", [">", ["get", "car_km"], 1000], 1, 0], 10, 1],
    },
  } as unknown as maplibregl.LayerSpecification);
  applyStyle();
}

function applyStyle(): void {
  if (!map.getLayer("roads")) return;
  const p = paint();
  for (const k in p) map.setPaintProperty("roads", k, p[k]);
  const shown = ["!", ["in", ["get", mode], ["literal", [...off[mode]]]]];
  // 式の型は maplibre の FilterSpecification に素直に合わないので unknown 経由で渡す
  map.setFilter("roads", shown as unknown as maplibregl.FilterSpecification);
  map.setFilter("roads-casing", ["all", emphasized(), shown] as unknown as maplibregl.FilterSpecification);
  if (!map.getLayer("muni-fill")) return;
  const ink = theme === "dark" ? "#f5f5f5" : "#111";
  map.setFilter("muni-outline", ["==", ["get", "code"], muni ?? ""] as unknown as maplibregl.FilterSpecification);
  map.setPaintProperty("muni-outline", "line-color", ink);
  map.setPaintProperty("muni-border", "line-color", ink);
  map.setLayoutProperty("muni-border", "visibility", showBorders ? "visible" : "none");
  map.setPaintProperty("muni-label", "text-color", theme === "dark" ? "#ffffff" : "#1a1a1a");
  map.setPaintProperty("muni-label", "text-halo-color", theme === "dark" ? "rgba(0,0,0,0.8)" : "rgba(255,255,255,0.9)");
  for (const id of ["muni-fill", "muni-label"]) map.setLayoutProperty(id, "visibility", showFill ? "visible" : "none");
}

// ---- 表示オプション(市区町村の色分け・行政区域の境界) ----
let showFill = kindOf(areas[current]) !== "city"; // 市区町村エリアは Z9 から線が出るので面塗りは切る
let showBorders = true;
const fillChk = document.getElementById("choropleth") as HTMLInputElement;
const bordersChk = document.getElementById("borders") as HTMLInputElement;
const scaleEl = document.getElementById("muni-scale") as HTMLElement;

function renderScale(): void {
  scaleEl.hidden = !showFill;
  if (showFill && !scaleEl.childElementCount) {
    scaleEl.innerHTML = MUNI_STEPS.map(([from, color], i) => {
      const to = MUNI_STEPS[i + 1]?.[0];
      const t = i === 0 ? `〜${to}` : to == null ? `${from}〜` : `${from}〜${to}`;
      return `<span class="scale-item"><span class="scale-sw" style="background:${color}"></span><span class="scale-t">${t}</span></span>`;
    }).join("");
  }
}
fillChk.checked = showFill;
bordersChk.checked = showBorders;
fillChk.addEventListener("change", () => { showFill = fillChk.checked; renderScale(); applyStyle(); });
bordersChk.addEventListener("change", () => { showBorders = bordersChk.checked; applyStyle(); });

// ---- テーマ・背景の切替(setStyle で全レイヤーが消えるので style.load 後に貼り直す) ----
async function reloadStyle(): Promise<void> {
  const style = await getBasemapStyle(base, theme);
  styleReady = false;
  map.setStyle(style, { diff: false });
}

const themeBtn = document.getElementById("theme-btn") as HTMLButtonElement;
const renderThemeBtn = (): void => { themeBtn.textContent = theme === "dark" ? "☀️" : "🌙"; };
themeBtn.addEventListener("click", () => {
  theme = theme === "dark" ? "light" : "dark";
  applyThemeAttr(theme);
  renderThemeBtn();
  void reloadStyle();
});

class BasemapControl implements maplibregl.IControl {
  private el!: HTMLElement;
  onAdd(): HTMLElement {
    this.el = document.createElement("div");
    this.el.className = "maplibregl-ctrl basemap-switch";
    for (const [b, name] of BASEMAPS) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = name;
      btn.dataset.base = b;
      btn.setAttribute("aria-selected", String(b === base));
      btn.addEventListener("click", () => {
        if (b === base) return;
        base = b;
        this.sync();
        void reloadStyle();
      });
      this.el.append(btn);
    }
    return this.el;
  }
  onRemove(): void { this.el.remove(); }
  sync(): void {
    for (const btn of this.el.querySelectorAll<HTMLButtonElement>("button")) btn.setAttribute("aria-selected", String(btn.dataset.base === base));
  }
}
map.addControl(new BasemapControl(), "bottom-right");

// ---- パネル開閉 ----
const panel = document.getElementById("panel") as HTMLElement;
const collapseBtn = document.getElementById("collapse-btn") as HTMLButtonElement;
const renderCollapseBtn = (): void => { collapseBtn.textContent = panel.classList.contains("collapsed") ? "▾" : "▴"; };
collapseBtn.addEventListener("click", () => { panel.classList.toggle("collapsed"); renderCollapseBtn(); });

// ---- エリア選択(全国 / 都道府県 / 市区町村) ----
const areaSel = document.getElementById("area") as HTMLSelectElement;
for (const [gk, gname] of [["japan", "全国"], ["prefecture", "都道府県"], ["city", "市区町村（詳細タイル）"]] as const) {
  // 都道府県・全国はタイル URL(全国 PMTiles)が入るまで出さない
  const entries = Object.entries(areas).filter(([, a]) => kindOf(a) === gk && (gk === "city" || a.tiles));
  if (!entries.length) continue;
  const og = document.createElement("optgroup");
  og.label = gname;
  for (const [k, a] of entries) og.appendChild(new Option(a.name, k));
  areaSel.appendChild(og);
}
areaSel.value = current;
areaSel.addEventListener("change", () => { setMuni(null, false); setArea(areaSel.value, true); });

function setArea(key: string, jump: boolean): void {
  current = key;
  areaSel.value = key;
  showFill = kindOf(areas[key]) !== "city";
  fillChk.checked = showFill;
  renderScale();
  syncUrl();
  renderLegend();
  addDataLayers();
  if (jump) map.jumpTo({ center: areas[key].view.center, zoom: areas[key].view.zoom });
}

function syncUrl(): void {
  history.replaceState(null, "", `?area=${current}${muni ? `&muni=${muni}` : ""}${location.hash}`);
}

// ---- 市区町村(全国から検索、地図クリックでも選べる) ----
// 集計は public/municipalities.json、面と代表点は tiles/municipalities.pmtiles
let muni: string | null = params.get("muni");
let munis: Record<string, MuniInfo> | null = null;
let pendingFit = initialNoHash && !!muni; // URL に市区町村があってハッシュが無ければ、読込後にその市区町村へ寄せる
const muniRank = new Map<string, number>();
let rankTotal = 0;
const muniInput = document.getElementById("muni-input") as HTMLInputElement;
const muniList = document.getElementById("muni-list") as HTMLDataListElement;
const labelToCode = new Map<string, string>();
const muniLabel = (m: MuniInfo): string => `${m.name}（${m.pref_name}）`;

async function initMuni(): Promise<void> {
  const all: Record<string, MuniInfo> = await (await fetch(`${BASE_URL}municipalities.json`)).json();
  munis = all;
  const frag = document.createDocumentFragment();
  for (const [code, m] of Object.entries(all).sort(([a], [b]) => a.localeCompare(b))) {
    const text = muniLabel(m);
    labelToCode.set(text, code);
    const o = document.createElement("option");
    o.value = text;
    frag.appendChild(o);
  }
  muniList.appendChild(frag);
  // 変更率の順位(政令市全体は区と重複するので除く)
  const ranked = Object.entries(all).filter(([, m]) => m.lv !== 2 && m.pct != null).sort((a, b) => b[1].pct! - a[1].pct!);
  ranked.forEach(([code], i) => muniRank.set(code, i + 1));
  rankTotal = ranked.length;
  if (muni && !all[muni]) muni = null;
  if (muni) { setMuni(muni, pendingFit); pendingFit = false; } else { renderLegend(); }
}

const syncMuniInput = (): void => { muniInput.value = muni && munis?.[muni] ? muniLabel(munis[muni]) : ""; };

/** 市区町村を選ぶ。タイルがその市区町村を含まないエリア(市区町村エリア)なら都道府県に切り替える。 */
function selectMuni(code: string): void {
  const m = munis?.[code];
  if (!m) return;
  const prefKey = `pref_${m.pref_code}`;
  if (!areas[current].tiles && areas[prefKey]) setArea(prefKey, false);
  setMuni(code, true);
}

function setMuni(code: string | null, jump: boolean): void {
  muni = code;
  syncMuniInput();
  syncUrl();
  renderLegend();
  applyStyle();
  if (jump && code && munis?.[code]) {
    const [w0, s0, e0, n0] = munis[code].bbox;
    // 初回(URL 指定)は即時、操作で選んだときはアニメーション
    map.fitBounds([[w0, s0], [e0, n0]], { padding: isMobile ? 24 : 40, maxZoom: 15, duration: map.getLayer("roads") ? 600 : 0 });
  }
}

muniInput.addEventListener("change", () => {
  const v = muniInput.value.trim();
  if (!v) { setMuni(null, false); return; }
  const code = labelToCode.get(v) ?? [...labelToCode].find(([text]) => text.startsWith(v))?.[1];
  if (code) selectMuni(code);
  else syncMuniInput(); // 候補に無い入力は元に戻す
});
(document.getElementById("muni-clear") as HTMLButtonElement).addEventListener("click", () => setMuni(null, false));

// ---- 表示モード(判定 / 改正前 / 改正後) ----
const modeDiv = document.getElementById("mode") as HTMLElement;
for (const m of MODES) {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.role = "tab";
  btn.textContent = m.name;
  btn.dataset.mode = m.key;
  btn.setAttribute("aria-selected", String(m.key === mode));
  btn.addEventListener("click", () => setMode(m.key));
  modeDiv.append(btn);
}
function setMode(m: Mode): void {
  mode = m;
  for (const b of modeDiv.querySelectorAll<HTMLButtonElement>("button")) b.setAttribute("aria-selected", String(b.dataset.mode === m));
  renderLegend();
  applyStyle();
}
document.addEventListener("keydown", (e) => {
  if (e.target instanceof HTMLInputElement) return; // 検索入力中のキーは拾わない
  if (e.key === "b" || e.key === "B") setMode(mode === "speed_before" ? "speed_after" : "speed_before");
});

// ---- 凡例(トグル) ----
const legendDiv = document.getElementById("legend") as HTMLElement;
const statEl = document.getElementById("stat") as HTMLElement;
const km = (v: number): string => `${Math.round(v).toLocaleString()} km`;

/** 集計の対象。市区町村を選んでいればその市区町村、でなければエリア全体。 */
function scopeTally(): Record<string, number> {
  const scope = (muni && munis ? munis[muni] : areas[current]) as { classes: Record<string, number>; speed_before?: Record<string, number>; speed_after?: Record<string, number> };
  return (mode === "final" ? scope.classes : mode === "speed_before" ? scope.speed_before : scope.speed_after) ?? {};
}

function renderLegend(): void {
  const a = areas[current];
  const m = muni && munis ? munis[muni] : null;
  const tally = scopeTally();
  ensureDefaults(mode, Object.keys(tally));
  legendDiv.innerHTML = "";
  for (const s of orderedClasses(mode, tally)) {
    const row = document.createElement("label");
    row.className = "toggle";
    const input = document.createElement("input");
    input.type = "checkbox";
    input.checked = !off[mode].has(s.value);
    input.addEventListener("change", () => { input.checked ? off[mode].delete(s.value) : off[mode].add(s.value); applyStyle(); });
    const sw = document.createElement("span");
    sw.className = "sw";
    sw.style.background = s.color;
    const text = document.createElement("span");
    text.className = "t-label";
    text.textContent = label(mode, s.value);
    const val = document.createElement("span");
    val.className = "t-km";
    val.textContent = km(tally[s.value]);
    row.append(input, sw, text, val);
    legendDiv.append(row);
  }
  // 要約。車道 = 中心線から軽車道・徒歩道等を除いたもの
  const changed = m ? m.changed_km : a.classes[CHANGED] ?? 0;
  const carKm = m ? m.car_km : a.official?.gsi_normal_total_km ?? a.total_km;
  const name = m ? `${m.pref_name} ${m.name}` : a.name;
  let s = `<b>${name}</b>: 車道 ${km(carKm)} のうち <b>${km(changed)}（${(changed / carKm * 100).toFixed(0)}%）</b>が 60→30 に変わったと推定`;
  if (!m && a.official) s += `。道路法上の道路に換算すると ${a.official.changed_share_pct[0]}〜${a.official.changed_share_pct[1]}%`;
  if (m) {
    const r = muniRank.get(muni!);
    if (r) s += `。変更率は全国 ${rankTotal.toLocaleString()} 市区町村中 <b>${r.toLocaleString()} 位</b>`;
    s += `。市区町村への割り当ては線分の中点で行い、道路法換算は都道府県のみ`;
  }
  s += `<span class="stat-meta">規制データ JARTIC ${a.jartic_month.slice(0, 4)}-${a.jartic_month.slice(4)} / 生成 ${a.generated}</span>`;
  statEl.innerHTML = s;
}

function setAll(on: boolean): void {
  if (on) off[mode].clear();
  else for (const k of Object.keys(scopeTally())) off[mode].add(k);
  renderLegend();
  applyStyle();
}
(document.getElementById("all-on") as HTMLButtonElement).addEventListener("click", () => setAll(true));
(document.getElementById("all-off") as HTMLButtonElement).addEventListener("click", () => setAll(false));

// ---- クリックで属性 ----
const esc = (v: unknown): string => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);
const pct = (v: unknown): string => (v == null || v === "" ? "-" : `${Math.round(Number(v) * 100)}%`);
const sp = (v: unknown): string => (/^\d+$/.test(String(v)) ? `${v} km/h` : label("speed_after", String(v)));
let popup: maplibregl.Popup | null = null;
map.on("click", "roads", (e) => {
  const p = (e.features?.[0]?.properties ?? {}) as Record<string, unknown>;
  const row = (k: string, v: string) => `<tr><th>${esc(k)}</th><td>${v}</td></tr>`;
  const rows = [
    row("速度", `${esc(sp(p.speed_before))} → <b>${esc(sp(p.speed_after))}</b>`),
    row("幅員区分", esc(WIDTH[String(p.rnkWidth)] ?? p.rnkWidth)),
    row("中央分離帯", String(p.medSect) === "0" ? "なし" : `${esc(p.medSect)} m`),
    row("道路分類", esc(CTG[String(p.rdCtg)] ?? p.rdCtg)),
  ];
  if (p.reg_speed) rows.push(row("速度規制", `${esc(p.reg_speed)} km/h（重なり ${pct(p.frac_speed)}）`));
  if (p.zone_speed) rows.push(row("面規制", `${esc(p.zone_speed)}（内包 ${pct(p.frac_zone)}）`));
  rows.push(row("区間長", `${Math.round(Number(p.len_m))} m`));
  popup?.remove();
  popup = new maplibregl.Popup({ closeButton: true, maxWidth: "300px" })
    .setLngLat(e.lngLat)
    .setHTML(`<div class="pop"><div class="pop-head">${esc(label("final", String(p.final)))}</div><table class="pop-tbl">${rows.join("")}</table></div>`)
    .addTo(map);
});

// 面をクリックしたらその市区町村を選ぶ。ホバーで名前と変更率を出す(マウスのある環境だけ)
map.on("click", "muni-fill", (e) => {
  const code = e.features?.[0]?.properties?.code as string | undefined;
  if (code) selectMuni(code);
});
if (window.matchMedia("(hover: hover)").matches) {
  map.on("mouseenter", "roads", () => { map.getCanvas().style.cursor = "pointer"; });
  map.on("mouseleave", "roads", () => { map.getCanvas().style.cursor = ""; });
  let hover: maplibregl.Popup | null = null;
  map.on("mousemove", "muni-fill", (e) => {
    const p = e.features?.[0]?.properties as Record<string, unknown> | undefined;
    if (!p) return;
    map.getCanvas().style.cursor = "pointer";
    hover ??= new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 10, className: "pop-hover" });
    hover
      .setLngLat(e.lngLat)
      .setHTML(`<div class="pop-mini"><b>${esc(p.name)}</b><span>${esc(p.pref_name)}</span><br>車道 ${km(Number(p.car_km))} / 変更 <b>${Math.round(Number(p.pct))}%</b></div>`)
      .addTo(map);
  });
  map.on("mouseleave", "muni-fill", () => { map.getCanvas().style.cursor = ""; hover?.remove(); });
}

// ---- 初期化 ----
const buildEl = document.getElementById("build-ver");
if (buildEl) buildEl.textContent = `build ${__BUILD_TIME__}`;
renderThemeBtn();
if (isMobile) panel.classList.add("collapsed"); // スマホは畳んで地図を広く
renderCollapseBtn();
renderScale();
renderLegend();
// 判定レイヤーは style.load ハンドラ(addDataLayers)が載せる。"load" はスプライト・全タイル待ちで遅いので使わない。
// 初回だけ URL にハッシュが無ければエリアの既定ビューへ移動する(市区町村指定があればそちらへ寄せる)
if (initialNoHash && !muni) map.once("style.load", () => map.jumpTo({ center: areas[current].view.center, zoom: areas[current].view.zoom }));
void initMuni();

// WebGL コンテキスト消失からの復帰(iOS Safari 等)
const canvas = map.getCanvas();
canvas.addEventListener("webglcontextlost", (ev) => ev.preventDefault(), false);
canvas.addEventListener("webglcontextrestored", () => addDataLayers(), false);

(window as unknown as { __map: maplibregl.Map }).__map = map;

// PWA: Service Worker(本番のみ)
if (import.meta.env.PROD && "serviceWorker" in navigator) {
  window.addEventListener("load", () => { navigator.serviceWorker.register(`${BASE_URL}sw.js`).catch(() => {}); });
  let refreshing = false;
  navigator.serviceWorker.addEventListener("controllerchange", () => { if (refreshing) return; refreshing = true; location.reload(); });
}
