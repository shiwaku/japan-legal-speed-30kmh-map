// 背景地図。国土地理院 最適化ベクトルタイルの淡色風(pale)・標準(std)、地理院タイルの全国最新写真、白図。
// pale.json / std.json は public/ に置いた静的スタイル(scripts/make_pale_style.py が地理院の std.json から生成)。
// ダークテーマは選択中のスタイルの色を明度反転して作る。
// dm-converter/viewer/src/basemap.ts を元に、DM スプライトの注入を外したもの。
import type { StyleSpecification } from "maplibre-gl";
import type { Theme } from "./theme";

function parseColor(str: string): [number, number, number, number] | null {
  const s = str.trim();
  const rgba = /^rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*(?:,\s*([\d.]+)\s*)?\)$/i.exec(s);
  if (rgba) return [+rgba[1], +rgba[2], +rgba[3], rgba[4] !== undefined ? +rgba[4] : 1];
  const hex = /^#([0-9a-f]{3}|[0-9a-f]{4}|[0-9a-f]{6}|[0-9a-f]{8})$/i.exec(s);
  if (hex) {
    let h = hex[1];
    if (h.length === 3 || h.length === 4) h = h.split("").map((c) => c + c).join("");
    const r = parseInt(h.slice(0, 2), 16), g = parseInt(h.slice(2, 4), 16), b = parseInt(h.slice(4, 6), 16);
    const a = h.length === 8 ? parseInt(h.slice(6, 8), 16) / 255 : 1;
    return [r, g, b, a];
  }
  return null;
}

function rgbToHsl(r: number, g: number, b: number): [number, number, number] {
  r /= 255; g /= 255; b /= 255;
  const max = Math.max(r, g, b), min = Math.min(r, g, b);
  const l = (max + min) / 2;
  let h = 0, s = 0;
  if (max !== min) {
    const d = max - min;
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    if (max === r) h = (g - b) / d + (g < b ? 6 : 0);
    else if (max === g) h = (b - r) / d + 2;
    else h = (r - g) / d + 4;
    h /= 6;
  }
  return [h, s, l];
}

function hslToRgb(h: number, s: number, l: number): [number, number, number] {
  if (s === 0) { const v = Math.round(l * 255); return [v, v, v]; }
  const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
  const p = 2 * l - q;
  const hue = (t: number): number => {
    if (t < 0) t += 1;
    if (t > 1) t -= 1;
    if (t < 1 / 6) return p + (q - p) * 6 * t;
    if (t < 1 / 2) return q;
    if (t < 2 / 3) return p + (q - p) * (2 / 3 - t) * 6;
    return p;
  };
  return [Math.round(hue(h + 1 / 3) * 255), Math.round(hue(h) * 255), Math.round(hue(h - 1 / 3) * 255)];
}

/** 明度を反転して暗色に(色相は保持、彩度は少し抑える)。 */
function darkenColor(str: string): string {
  const c = parseColor(str);
  if (!c) return str;
  const [r, g, b, a] = c;
  const [h, s, l] = rgbToHsl(r, g, b);
  const nl = Math.min(0.9, Math.max(0.05, 1 - l));
  const [nr, ng, nb] = hslToRgb(h, s * 0.85, nl);
  return `rgba(${nr},${ng},${nb},${a})`;
}

function transformValue(v: unknown, fn: (s: string) => string): unknown {
  if (typeof v === "string") return parseColor(v) ? fn(v) : v;
  if (Array.isArray(v)) return v.map((x) => transformValue(x, fn));
  return v;
}

function recolor(src: StyleSpecification, fn: (s: string) => string): StyleSpecification {
  const style = structuredClone(src) as StyleSpecification;
  for (const layer of style.layers) {
    const paint = (layer as { paint?: Record<string, unknown> }).paint;
    if (!paint) continue;
    for (const key of Object.keys(paint)) {
      if (key.includes("color")) paint[key] = transformValue(paint[key], fn);
    }
  }
  return style;
}

export type Basemap = "pale" | "std" | "photo" | "blank";
export const BASEMAPS: [Basemap, string][] = [
  ["pale", "淡色"],
  ["std", "標準"],
  ["photo", "写真"],
  ["blank", "白図"],
];

const GLYPHS = "https://gsi-cyberjapan.github.io/optimal_bvmap/glyphs/{fontstack}/{range}.pbf";
const rawCache = new Map<string, StyleSpecification>();
const styleCache = new Map<string, StyleSpecification>();

async function loadRaw(name: "pale" | "std"): Promise<StyleSpecification> {
  const hit = rawCache.get(name);
  if (hit) return hit;
  const res = await fetch(`${import.meta.env.BASE_URL}${name}.json`);
  const style = (await res.json()) as StyleSpecification;
  rawCache.set(name, style);
  return style;
}

function photoStyle(): StyleSpecification {
  return {
    version: 8,
    glyphs: GLYPHS,
    sources: {
      photo: {
        type: "raster",
        tiles: ["https://cyberjapandata.gsi.go.jp/xyz/seamlessphoto/{z}/{x}/{y}.jpg"],
        tileSize: 256,
        maxzoom: 18,
        attribution: '<a href="https://maps.gsi.go.jp/development/ichiran.html" target="_blank" rel="noopener">地理院タイル(全国最新写真)</a>',
      },
    },
    layers: [{ id: "photo", type: "raster", source: "photo", paint: { "raster-saturation": -0.3, "raster-brightness-max": 0.9 } }],
  } as StyleSpecification;
}

function blankStyle(theme: Theme): StyleSpecification {
  return {
    version: 8,
    glyphs: GLYPHS,
    sources: {},
    layers: [{ id: "background", type: "background", paint: { "background-color": theme === "dark" ? "#14161a" : "#ffffff" } }],
  } as StyleSpecification;
}

export async function getBasemapStyle(base: Basemap, theme: Theme): Promise<StyleSpecification> {
  if (base === "photo") return photoStyle();
  if (base === "blank") return blankStyle(theme);
  const key = `${base}-${theme}`;
  const cached = styleCache.get(key);
  if (cached) return cached;
  const src = await loadRaw(base);
  const style = theme === "dark" ? recolor(src, darkenColor) : src;
  styleCache.set(key, style);
  return style;
}

/** 判定レイヤーを差し込む位置。地理院スタイルでは「注記〜」の symbol 群の直前(建物・道路の上、注記の下)。 */
export function insertBeforeId(style: StyleSpecification): string | undefined {
  return style.layers.find((l) => l.type === "symbol" && l.id.startsWith("注記"))?.id;
}
