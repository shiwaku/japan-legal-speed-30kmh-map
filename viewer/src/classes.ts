// 判定区分・速度の表示順と色。scripts/common.py の FINAL_STYLE / SPEED_STYLE と同じ。
// タイルの属性値(データ上の区分名)は変えず、表示ラベルだけ DISPLAY で置き換える。

export type Mode = "final" | "speed_before" | "speed_after";

export interface ClassStyle {
  value: string;
  color: string;
  on: boolean;
}

export const FINAL_STYLE: ClassStyle[] = [
  { value: "★60→30 変更(推定)", color: "#d62728", on: true },
  { value: "不明:幅員5.5m以上(中央線有無不明)", color: "#ff9f1c", on: true },
  { value: "規制あり:標識30", color: "#9ecae1", on: true },
  { value: "規制あり:標識40", color: "#4292c6", on: true },
  { value: "規制あり:標識50", color: "#08519c", on: true },
  { value: "規制あり:標識60", color: "#08306b", on: true },
  { value: "規制あり:標識80", color: "#08306b", on: true },
  { value: "規制あり:ゾーン30", color: "#74c476", on: true },
  { value: "対象外:車両通行帯あり", color: "#756bb1", on: true },
  { value: "対象外:中央線(JARTIC)", color: "#54278f", on: true },
  { value: "対象外:分離帯あり", color: "#636363", on: true },
  { value: "対象外:高速等", color: "#000000", on: true },
  { value: "不明:属性不明", color: "#e377c2", on: true },
  { value: "非通常道路(ftCode)", color: "#bdbdbd", on: false },
];

export const SPEED_STYLE: ClassStyle[] = [
  { value: "20", color: "#7f0000", on: true },
  { value: "30", color: "#d62728", on: true },
  { value: "40", color: "#ff7f0e", on: true },
  { value: "50", color: "#2ca02c", on: true },
  { value: "60", color: "#1f77b4", on: true },
  { value: "80", color: "#08306b", on: true },
  { value: "100", color: "#08306b", on: true },
  { value: "不明(60/30)", color: "#ff9f1c", on: true },
  { value: "高速", color: "#000000", on: true },
  { value: "対象外", color: "#bdbdbd", on: false },
];

export const CHANGED = FINAL_STYLE[0].value;

const DISPLAY: Record<string, string> = {
  "★60→30 変更(推定)": "60→30 に変わった（推定）",
  "不明:幅員5.5m以上(中央線有無不明)": "不明（幅 5.5 m 以上）",
  "不明:属性不明": "不明（幅のデータなし）",
  "規制あり:ゾーン30": "ゾーン30（変わらない）",
  "対象外:車両通行帯あり": "対象外: 車両通行帯あり",
  "対象外:中央線(JARTIC)": "対象外: 中央線あり",
  "対象外:分離帯あり": "対象外: 中央分離帯あり",
  "対象外:高速等": "対象外: 高速道路",
  "非通常道路(ftCode)": "車道以外（軽車道・徒歩道）",
  "対象外": "車道以外",
  "不明(60/30)": "不明（60 か 30）",
  "高速": "高速道路",
};

/** 区分名の表示ラベル。「規制あり:標識40」→「標識 40 km/h（変わらない）」。 */
export function label(mode: Mode, value: string): string {
  if (mode !== "final") return /^\d+$/.test(value) ? `${value} km/h` : DISPLAY[value] ?? value;
  const m = /^規制あり:標識(\d+)$/.exec(value);
  if (m) return `標識 ${m[1]} km/h（変わらない）`;
  return DISPLAY[value] ?? value;
}

export const MODES: { key: Mode; name: string; style: ClassStyle[] }[] = [
  { key: "final", name: "判定", style: FINAL_STYLE },
  { key: "speed_before", name: "改正前", style: SPEED_STYLE },
  { key: "speed_after", name: "改正後", style: SPEED_STYLE },
];

export const WIDTH: Record<string, string> = { 0: "3 m 未満", 1: "3〜5.5 m", 2: "5.5〜13 m", 3: "13〜19.5 m", 4: "19.5 m 以上", 5: "その他", 6: "不明" };
export const CTG: Record<string, string> = { 0: "国道", 1: "都道府県道", 2: "市区町村道", 3: "高速自動車国道等", 5: "その他", 6: "不明" };

/** docs/areas.json(= public/areas.json)の 1 エリア。scripts/05 と make_national_summary が書く。 */
export interface AreaInfo {
  name: string;
  kind?: "japan" | "prefecture" | "city";
  pref_code?: string;
  view: { center: [number, number]; zoom: number };
  tiles?: string | null;
  jartic_month: string;
  buffer_m: number;
  generated: string;
  total_km: number;
  classes: Record<string, number>;
  speed_before?: Record<string, number>;
  speed_after?: Record<string, number>;
  official?: {
    official_total_km: number;
    gsi_normal_total_km: number;
    excess_km: number;
    structural_share_pct: [number, number];
    changed_share_pct: [number, number];
  } | null;
  official_width?: { share_lt_5_5m_pct?: number } | null;
}

/** public/municipalities.json の 1 市区町村(scripts/make_municipalities.py が書く)。政令市は区と市全体(コード XX1x0)の両方がある。 */
export interface MuniInfo {
  name: string;
  pref_code: string;
  city: string;
  ward: string;
  bbox: [number, number, number, number];
  total_km: number;
  classes: Record<string, number>;
  speed_before: Record<string, number>;
  speed_after: Record<string, number>;
}
