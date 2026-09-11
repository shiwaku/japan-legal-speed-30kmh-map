import maplibregl from "maplibre-gl";
import { Protocol } from "pmtiles";
import "maplibre-gl/dist/maplibre-gl.css";

import { BASEMAPS, getBasemapStyle, insertBeforeId, type Basemap } from "./basemap";
import { CHANGED, CTG, MODES, WIDTH, label, type AreaInfo, type Mode, type MuniInfo } from "./classes";
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

// 表示クラス(モードごと)。既定は classes.ts の on
const enabled: Record<Mode, Set<string>> = {
  final: new Set(MODES[0].style.filter((s) => s.on).map((s) => s.value)),
  speed_before: new Set(MODES[1].style.filter((s) => s.on).map((s) => s.value)),
  speed_after: new Set(MODES[2].style.filter((s) => s.on).map((s) => s.value)),
};

// ---- 地図 ----
const view = areas[current].view;
const map = new maplibregl.Map({
  container: "map",
  style: await getBasemapStyle(base, theme),
  center: view.center,
  zoom: view.zoom,
  minZoom: 5,
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
const paint = () => {
  const st = MODES.find((m) => m.key === mode)!.style;
  return {
    "line-color": ["match", ["get", mode], ...st.flatMap((s) => [s.value, s.color]), "#999"],
    "line-width": w(["case", emphasized(), 0.8, 1.0], ["case", emphasized(), 2.2, 2.4], 6),
    "line-opacity": ["case", ["in", ["get", mode], ["literal", ["非通常道路(ftCode)", "対象外"]]], 0.5, 0.95],
  } as Record<string, unknown>;
};

// setStyle 直後はスタイル読込中で addSource が例外になる。読込完了は style.load 側で拾って載せ直す
let styleReady = false;
map.on("style.load", () => { styleReady = true; addDataLayers(); });

function addDataLayers(): void {
  if (!styleReady) return;
  const a = areas[current];
  if (map.getSource("roads")) {
    for (const id of ["roads", "roads-casing"]) if (map.getLayer(id)) map.removeLayer(id);
    map.removeSource("roads");
  }
  map.addSource("roads", { type: "vector", url: `pmtiles://${tilesUrl(current, a)}` });
  // 背景地図の注記より下、建物・道路より上に差し込む(写真・白図では最上位)
  const before = insertBeforeId(map.getStyle());
  map.addLayer(
    { id: "roads-casing", type: "line", source: "roads", "source-layer": "roads", paint: { "line-color": "#fff", "line-width": w(1.2, 3.5, 9), "line-opacity": 0.7 } } as maplibregl.LayerSpecification,
    before,
  );
  map.addLayer(
    { id: "roads", type: "line", source: "roads", "source-layer": "roads", layout: { "line-cap": "round", "line-join": "round" }, paint: paint() } as maplibregl.LayerSpecification,
    before,
  );
  // 行政区域(国土数値情報 N03)。全市区町村の境界線と、選択中の市区町村の強調(判定線の上、注記の下)
  map.addSource("muni", { type: "vector", url: `pmtiles://${location.origin}${BASE_URL}tiles/municipalities.pmtiles` });
  map.addLayer(
    { id: "muni-border", type: "line", source: "muni", "source-layer": "muni", layout: { "line-join": "round" }, paint: { "line-color": "#111", "line-width": w(0.8, 1.2, 2), "line-opacity": 0.55 } } as unknown as maplibregl.LayerSpecification,
    before,
  );
  map.addLayer(
    { id: "muni-outline", type: "line", source: "muni", "source-layer": "muni", filter: ["==", ["get", "code"], ""], layout: { "line-join": "round" }, paint: { "line-color": "#111", "line-width": w(2, 3, 5), "line-dasharray": [2, 1.5], "line-opacity": 0.95 } } as unknown as maplibregl.LayerSpecification,
    before,
  );
  applyStyle();
}

function applyStyle(): void {
  if (!map.getLayer("roads")) return;
  const p = paint();
  for (const k in p) map.setPaintProperty("roads", k, p[k]);
  const list = ["literal", [...enabled[mode]]];
  // 式の型は maplibre の FilterSpecification に素直に合わないので unknown 経由で渡す
  map.setFilter("roads", ["in", ["get", mode], list] as unknown as maplibregl.FilterSpecification);
  map.setFilter("roads-casing", ["all", emphasized(), ["in", ["get", mode], list]] as unknown as maplibregl.FilterSpecification);
  if (map.getLayer("muni-outline")) {
    map.setFilter("muni-outline", ["==", ["get", "code"], muni ?? ""] as unknown as maplibregl.FilterSpecification);
    const ink = theme === "dark" ? "#f5f5f5" : "#111";
    map.setPaintProperty("muni-outline", "line-color", ink);
    map.setPaintProperty("muni-border", "line-color", ink);
    map.setLayoutProperty("muni-border", "visibility", showBorders ? "visible" : "none");
  }
}

// ---- 行政区域の表示切替 ----
let showBorders = true;
const bordersChk = document.getElementById("borders") as HTMLInputElement;
bordersChk.checked = showBorders;
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
for (const [gk, gname] of [["japan", "全国"], ["prefecture", "都道府県"], ["city", "市区町村"]] as const) {
  // 都道府県・全国はタイル URL(全国 PMTiles)が入るまで出さない
  const entries = Object.entries(areas).filter(([, a]) => kindOf(a) === gk && (gk === "city" || a.tiles));
  if (!entries.length) continue;
  const og = document.createElement("optgroup");
  og.label = gname;
  for (const [k, a] of entries) og.appendChild(new Option(a.name, k));
  areaSel.appendChild(og);
}
areaSel.value = current;
areaSel.addEventListener("change", () => { muni = null; setArea(areaSel.value, true); });

function setArea(key: string, jump: boolean): void {
  current = key;
  areaSel.value = key;
  syncUrl();
  void renderMuniSelect();
  renderLegend();
  addDataLayers();
  if (jump) map.jumpTo({ center: areas[key].view.center, zoom: areas[key].view.zoom });
}

function syncUrl(): void {
  history.replaceState(null, "", `?area=${current}${muni ? `&muni=${muni}` : ""}${location.hash}`);
}

// ---- 市区町村(都道府県を選んだときだけ)。集計は public/municipalities.json、輪郭は tiles/municipalities.pmtiles ----
let muni: string | null = params.get("muni");
let munis: Record<string, MuniInfo> | null = null;
let pendingFit = initialNoHash && !!muni; // URL に市区町村があってハッシュが無ければ、読込後にその市区町村へ寄せる
const muniField = document.getElementById("muni-field") as HTMLElement;
const muniSel = document.getElementById("muni") as HTMLSelectElement;
const loadMunis = async (): Promise<Record<string, MuniInfo>> =>
  (munis ??= await (await fetch(`${BASE_URL}municipalities.json`)).json());

async function renderMuniSelect(): Promise<void> {
  const a = areas[current];
  if (kindOf(a) !== "prefecture" || !a.pref_code) {
    muniField.hidden = true;
    muni = null;
    return;
  }
  const all = await loadMunis();
  if (kindOf(areas[current]) !== "prefecture") return; // 読込中に切り替わった
  const list = Object.entries(all).filter(([, m]) => m.pref_code === a.pref_code).sort(([x], [y]) => x.localeCompare(y));
  muniSel.innerHTML = "";
  muniSel.appendChild(new Option(`${a.name} 全体`, ""));
  for (const [code, m] of list) muniSel.appendChild(new Option(m.ward ? `　${m.ward}` : m.name, code)); // 政令市の区は字下げ
  if (muni && !all[muni]) muni = null;
  muniSel.value = muni ?? "";
  muniField.hidden = false;
  if (muni) { setMuni(muni, pendingFit); pendingFit = false; }
}
muniSel.addEventListener("change", () => setMuni(muniSel.value || null, true));

function setMuni(code: string | null, jump: boolean): void {
  muni = code;
  muniSel.value = code ?? "";
  syncUrl();
  renderLegend();
  applyStyle();
  if (jump && code && munis?.[code]) {
    const [w0, s0, e0, n0] = munis[code].bbox;
    // 初回(URL 指定)は即時、操作で選んだときはアニメーション
    map.fitBounds([[w0, s0], [e0, n0]], { padding: isMobile ? 24 : 40, maxZoom: 15, duration: munis && map.getLayer("roads") ? 600 : 0 });
  } else if (jump && !code) {
    map.jumpTo({ center: areas[current].view.center, zoom: areas[current].view.zoom });
  }
}

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
  if (e.key === "b" || e.key === "B") setMode(mode === "speed_before" ? "speed_after" : "speed_before");
});

// ---- 凡例(トグル) ----
const legendDiv = document.getElementById("legend") as HTMLElement;
const statEl = document.getElementById("stat") as HTMLElement;
const km = (v: number): string => `${Math.round(v).toLocaleString()} km`;

function renderLegend(): void {
  const a = areas[current];
  const m = muni && munis ? munis[muni] : null; // 市区町村を選んでいれば凡例・集計はその市区町村のもの
  const scope = m ?? a;
  const tally: Record<string, number> = (mode === "final" ? scope.classes : mode === "speed_before" ? scope.speed_before : scope.speed_after) ?? {};
  legendDiv.innerHTML = "";
  for (const s of MODES.find((m) => m.key === mode)!.style) {
    const v = tally[s.value];
    if (v == null) continue; // このエリアに無い区分は出さない
    const row = document.createElement("label");
    row.className = "toggle";
    const input = document.createElement("input");
    input.type = "checkbox";
    input.checked = enabled[mode].has(s.value);
    input.addEventListener("change", () => { input.checked ? enabled[mode].add(s.value) : enabled[mode].delete(s.value); applyStyle(); });
    const sw = document.createElement("span");
    sw.className = "sw";
    sw.style.background = s.color;
    const text = document.createElement("span");
    text.className = "t-label";
    text.textContent = label(mode, s.value);
    const val = document.createElement("span");
    val.className = "t-km";
    val.textContent = km(v);
    row.append(input, sw, text, val);
    legendDiv.append(row);
  }
  const changed = scope.classes[CHANGED] ?? 0;
  // 車道 = 中心線から軽車道・徒歩道等を除いたもの。市区町村は道路統計(都道府県単位)が無いので車道比だけ
  const carKm = m ? m.total_km - (m.classes["非通常道路(ftCode)"] ?? 0) : a.official?.gsi_normal_total_km ?? a.total_km;
  const name = m ? `${a.name} ${m.name}` : a.name;
  let s = `<b>${name}</b>: 車道 ${km(carKm)} のうち <b>${km(changed)}（${(changed / carKm * 100).toFixed(0)}%）</b>が 60→30 に変わったと推定`;
  if (!m && a.official) s += `。道路法上の道路に換算すると ${a.official.changed_share_pct[0]}〜${a.official.changed_share_pct[1]}%`;
  if (m) s += `。市区町村への割り当ては線分の中点で行い、道路法換算は都道府県のみ`;
  s += `<span class="stat-meta">規制データ JARTIC ${a.jartic_month.slice(0, 4)}-${a.jartic_month.slice(4)} / 生成 ${a.generated}</span>`;
  statEl.innerHTML = s;
}

function setAll(on: boolean): void {
  const st = MODES.find((m) => m.key === mode)!.style;
  for (const s of st) on ? enabled[mode].add(s.value) : enabled[mode].delete(s.value);
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
if (window.matchMedia("(hover: hover)").matches) {
  map.on("mouseenter", "roads", () => { map.getCanvas().style.cursor = "pointer"; });
  map.on("mouseleave", "roads", () => { map.getCanvas().style.cursor = ""; });
}

// ---- 初期化 ----
const buildEl = document.getElementById("build-ver");
if (buildEl) buildEl.textContent = `build ${__BUILD_TIME__}`;
renderThemeBtn();
if (isMobile) panel.classList.add("collapsed"); // スマホは畳んで地図を広く
renderCollapseBtn();
renderLegend();
// 判定レイヤーは style.load ハンドラ(addDataLayers)が載せる。"load" はスプライト・全タイル待ちで遅いので使わない。
// 初回だけ URL にハッシュが無ければエリアの既定ビューへ移動する(市区町村指定があればそちらへ寄せる)
if (initialNoHash && !muni) map.once("style.load", () => map.jumpTo({ center: areas[current].view.center, zoom: areas[current].view.zoom }));
void renderMuniSelect();

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
