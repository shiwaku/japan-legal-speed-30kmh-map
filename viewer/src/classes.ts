// 判定区分・速度の表示順と色。scripts/common.py の FINAL_STYLE / SPEED_STYLE と同じ。
// タイルの属性値(データ上の区分名)は変えず、表示ラベルだけ DISPLAY で置き換える。
// 表にない区分名が来ても凡例に出す(orderedClasses)。区分名は言い換えられることがあるため。
// 凡例は legendRows() でまとめる: 60 km/h 以上の標識のように「変わらない」ことだけが分かれば十分な
// 区分は 1 行にする(細かい内訳はクリックしたときのポップアップで出る)。

export type Mode = "final" | "speed_before" | "speed_after";

export interface ClassStyle {
  value: string;
  color: string;
  on: boolean;
}

// 同じ凡例行にまとめる区分は同じ色にしてある(凡例の色見本と地図の線の色を一致させる)
export const FINAL_STYLE: ClassStyle[] = [
  { value: "★60→30 変更(推定)", color: "#d62728", on: true },
  { value: "不明:幅員5.5m以上(中央線有無不明)", color: "#ff9f1c", on: true },
  { value: "規制あり:標識0", color: "#deebf7", on: true },
  { value: "規制あり:標識20", color: "#deebf7", on: true },
  { value: "規制あり:標識30", color: "#9ecae1", on: true },
  { value: "規制あり:標識40", color: "#4292c6", on: true },
  { value: "規制あり:標識50", color: "#2171b5", on: true },
  { value: "規制あり:標識60", color: "#08306b", on: true },
  { value: "規制あり:標識70", color: "#08306b", on: true },
  { value: "規制あり:標識80", color: "#08306b", on: true },
  { value: "規制あり:標識90", color: "#08306b", on: true },
  { value: "規制あり:標識100", color: "#08306b", on: true },
  { value: "規制あり:標識120", color: "#08306b", on: true },
  { value: "規制あり:ゾーン0", color: "#c7e9c0", on: true },
  { value: "規制あり:ゾーン20", color: "#c7e9c0", on: true },
  { value: "規制あり:ゾーン30", color: "#74c476", on: true },
  { value: "規制あり:ゾーン40", color: "#238b45", on: true },
  { value: "対象外:車両通行帯あり", color: "#756bb1", on: true },
  { value: "対象外:中央線(JARTIC)", color: "#54278f", on: true },
  { value: "対象外:分離帯あり", color: "#636363", on: true },
  { value: "対象外:高速等", color: "#000000", on: true },
  { value: "不明:属性不明", color: "#e377c2", on: true },
  // 車道以外。区分名は 2026-09 に言い換えたので新旧どちらも載せる(タイルは作った時点の名前)
  { value: "非車道(軽車道・徒歩道等を除く)(ftCode)", color: "#bdbdbd", on: false },
  { value: "非通常道路(ftCode)", color: "#bdbdbd", on: false },
];

export const SPEED_STYLE: ClassStyle[] = [
  { value: "0", color: "#7f0000", on: true },
  { value: "20", color: "#7f0000", on: true },
  { value: "30", color: "#d62728", on: true },
  { value: "40", color: "#ff7f0e", on: true },
  { value: "50", color: "#2ca02c", on: true },
  { value: "60", color: "#1f77b4", on: true },
  { value: "70", color: "#08306b", on: true },
  { value: "80", color: "#08306b", on: true },
  { value: "90", color: "#08306b", on: true },
  { value: "100", color: "#08306b", on: true },
  { value: "120", color: "#08306b", on: true },
  { value: "不明(60/30)", color: "#ff9f1c", on: true },
  { value: "高速", color: "#000000", on: true },
  { value: "対象外", color: "#bdbdbd", on: false },
];

export const CHANGED = FINAL_STYLE[0].value;

/** 表にない区分名の色。 */
const FALLBACK_COLOR = "#999999";

const DISPLAY: Record<string, string> = {
  "★60→30 変更(推定)": "60→30 に変わった（推定）",
  "不明:幅員5.5m以上(中央線有無不明)": "不明（幅 5.5 m 以上）",
  "不明:属性不明": "不明（幅のデータなし）",
  "対象外:車両通行帯あり": "対象外: 車両通行帯あり",
  "対象外:中央線(JARTIC)": "対象外: 中央線あり",
  "対象外:分離帯あり": "対象外: 中央分離帯あり",
  "対象外:高速等": "対象外: 高速道路",
  "非車道(軽車道・徒歩道等を除く)(ftCode)": "車道以外（軽車道・徒歩道）",
  "非通常道路(ftCode)": "車道以外（軽車道・徒歩道）",
  "対象外": "車道以外",
  "不明(60/30)": "不明（60 か 30）",
  "高速": "高速道路",
};

/** 区分名の表示ラベル。「規制あり:標識40」→「標識 40 km/h（変わらない）」。 */
export function label(mode: Mode, value: string): string {
  if (mode !== "final") return /^\d+$/.test(value) ? `${value} km/h` : DISPLAY[value] ?? value;
  const sign = /^規制あり:標識(\d+)$/.exec(value);
  if (sign) return `標識 ${sign[1]} km/h（変わらない）`;
  const zone = /^規制あり:ゾーン(\d+)$/.exec(value);
  if (zone) return `ゾーン${zone[1]}（変わらない）`;
  return DISPLAY[value] ?? value;
}

export const MODES: { key: Mode; name: string; style: ClassStyle[] }[] = [
  { key: "final", name: "判定", style: FINAL_STYLE },
  { key: "speed_before", name: "改正前", style: SPEED_STYLE },
  { key: "speed_after", name: "改正後", style: SPEED_STYLE },
];

/** 既定で非表示にする区分か。表にないものは「車道以外」だけ隠す。 */
export function defaultOff(mode: Mode, value: string): boolean {
  const known = MODES.find((m) => m.key === mode)!.style.find((s) => s.value === value);
  if (known) return !known.on;
  return mode === "final" ? value.endsWith("(ftCode)") : value === "対象外";
}

function colorOf(mode: Mode, value: string): string {
  return MODES.find((m) => m.key === mode)!.style.find((s) => s.value === value)?.color ?? FALLBACK_COLOR;
}

/**
 * 凡例に出す区分。既知のものは表の順、表にないものは延長の大きい順で後ろに足す。
 * tally はエリアの classes / speed_before / speed_after。
 */
export function orderedClasses(mode: Mode, tally: Record<string, number>): ClassStyle[] {
  const st = MODES.find((m) => m.key === mode)!.style;
  const known = st.filter((s) => tally[s.value] != null);
  const rest = Object.keys(tally)
    .filter((v) => !st.some((s) => s.value === v))
    .sort((a, b) => tally[b] - tally[a])
    .map((value) => ({ value, color: FALLBACK_COLOR, on: !defaultOff(mode, value) }));
  return [...known, ...rest];
}

/** 凡例の節。判定モードだけ使う(速度モードは全部 km/h なので分けない)。 */
export const SECTIONS = { changed: "60→30", same: "変わらない（規制あり）", out: "対象外", other: "その他" } as const;

/**
 * この区分をどの凡例行・どの節に入れるか。
 * 引き下げと関係のない区分(標識 60 km/h 以上など)は 1 行にまとめ、節見出しに任せてラベルを短くする。
 */
function groupOf(mode: Mode, value: string): { key: string; label: string; section?: string } {
  if (mode === "final") {
    const sign = /^規制あり:標識(\d+)$/.exec(value);
    if (sign) {
      const v = Number(sign[1]);
      // 60 以上は幅の広い道で、そもそも引き下げの対象外。20 以下はデータ上の 0 km/h を含む
      if (v >= 60) return { key: "sign-60up", label: "標識 60 km/h 以上", section: SECTIONS.same };
      if (v <= 20) return { key: "sign-le20", label: "標識 20 km/h 以下", section: SECTIONS.same };
      return { key: `sign-${v}`, label: `標識 ${v} km/h`, section: SECTIONS.same };
    }
    const zone = /^規制あり:ゾーン(\d+)$/.exec(value);
    if (zone) {
      const v = Number(zone[1]);
      if (v < 30) return { key: "zone-le20", label: "ゾーン20 以下", section: SECTIONS.same };
      return { key: `zone-${v}`, label: `ゾーン${v}`, section: SECTIONS.same };
    }
    if (value.startsWith("対象外")) {
      return { key: value, label: (DISPLAY[value] ?? value).replace(/^対象外: ?/, ""), section: SECTIONS.out };
    }
    if (value === CHANGED || value.startsWith("不明:幅員")) {
      return { key: value, label: label(mode, value), section: SECTIONS.changed };
    }
    return { key: value, label: label(mode, value), section: SECTIONS.other };
  }
  if (/^\d+$/.test(value)) {
    const v = Number(value);
    if (v >= 70) return { key: "sp-70up", label: "70 km/h 以上" };
    if (v <= 20) return { key: "sp-le20", label: "20 km/h 以下" };
    return { key: `sp-${v}`, label: `${v} km/h` };
  }
  return { key: value, label: label(mode, value) };
}

export interface LegendRow {
  key: string;
  label: string;
  /** 節見出し。前の行と同じなら見出しは出さない(判定モードのみ) */
  section?: string;
  color: string;
  /** この行に含まれるデータ上の区分名(表示 ON/OFF はまとめて効く) */
  values: string[];
  km: number;
}

/** 凡例の行。まとめた区分は延長を合計し、色は先頭の区分の色(まとめる区分は同色にしてある)。 */
export function legendRows(mode: Mode, tally: Record<string, number>): LegendRow[] {
  const rows: LegendRow[] = [];
  const index = new Map<string, LegendRow>();
  for (const s of orderedClasses(mode, tally)) {
    const g = groupOf(mode, s.value);
    const hit = index.get(g.key);
    if (hit) {
      hit.values.push(s.value);
      hit.km += tally[s.value] ?? 0;
      continue;
    }
    const row: LegendRow = { key: g.key, label: g.label, section: g.section, color: colorOf(mode, s.value), values: [s.value], km: tally[s.value] ?? 0 };
    index.set(g.key, row);
    rows.push(row);
  }
  return rows;
}

/** 市区町村の面塗り(変更率 %)。step 式の区切りと色。実データの分布(中央値 79%、10% 分位 62%、90% 分位 87%)に合わせた。 */
export const MUNI_STEPS: [number, string][] = [
  [0, "#fee5d9"],
  [60, "#fcae91"],
  [70, "#fb6a4a"],
  [78, "#de2d26"],
  [84, "#a50f15"],
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

/** public/municipalities.json の 1 市区町村(scripts/make_municipalities.py が書く)。 */
export interface MuniInfo {
  name: string;
  pref_code: string;
  pref_name: string;
  city: string;
  ward: string;
  /** 0=市区町村, 1=政令市の区, 2=政令市全体(区と重なるので面塗り・境界線からは外す) */
  lv: 0 | 1 | 2;
  bbox: [number, number, number, number];
  total_km: number;
  car_km: number;
  changed_km: number;
  pct: number | null;
  classes: Record<string, number>;
  speed_before: Record<string, number>;
  speed_after: Record<string, number>;
}
