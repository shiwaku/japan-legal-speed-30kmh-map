// npa-traffic-accident-converter/viewer/src/filters.ts から移植(変更なし)
import type { ExpressionSpecification } from "maplibre-gl";

export interface FilterState {
  naiyou: Set<string>; // 死亡事故 / 負傷事故
  years: Set<string>; // "2019".."2024"
  tyuya: Set<string>; // 昼 / 夜（「昼夜」ラベルの先頭1文字）
  party: string; // 関与当事者カテゴリのキー（"" = すべて）
  age: string; // 年齢階層ラベル（"" = すべて）。当事者A/Bいずれか該当で表示
}

const ALL_NAIYOU = ["死亡事故", "負傷事故"];
const ALL_YEARS = ["2019", "2020", "2021", "2022", "2023", "2024"];
const ALL_TYUYA = ["昼", "夜"];

// 当事者種別ラベルへのマッチ条件。prefix はラベル先頭一致、exact は完全一致。
// 「原付自転車」「特定小型原付自転車」が『自転車』の部分一致に紛れ込むため exact リストで区別する。
const PARTY_CATEGORIES: Record<string, { prefix?: string; exact?: string[] }> = {
  pedestrian: { exact: ["歩行者"] },
  bicycle: { exact: ["軽車両－自転車", "軽車両－駆動補助機付自転車"] },
  motorcycle: { prefix: "二輪車" },
  kickboard: { exact: ["特定小型原付自転車"] },
  passenger: { prefix: "乗用車" },
  cargo: { prefix: "貨物車" },
};

function partyCondition(field: string, key: string): ExpressionSpecification {
  const cat = PARTY_CATEGORIES[key];
  if (cat.prefix) {
    return ["==", ["slice", ["get", field], 0, cat.prefix.length], cat.prefix];
  }
  return ["in", ["get", field], ["literal", cat.exact ?? []]];
}

export function buildFilter(state: FilterState): ExpressionSpecification {
  const conditions: ExpressionSpecification[] = [];

  if (state.naiyou.size === 0) {
    return ["==", ["get", "事故内容"], "__none__"];
  }
  if (state.naiyou.size < ALL_NAIYOU.length) {
    conditions.push(["in", ["get", "事故内容"], ["literal", [...state.naiyou]]]);
  }

  if (state.years.size === 0) {
    return ["==", ["get", "事故内容"], "__none__"];
  }
  if (state.years.size < ALL_YEARS.length) {
    conditions.push([
      "in",
      ["to-string", ["get", "発生日時_年"]],
      ["literal", [...state.years]],
    ]);
  }

  if (state.tyuya.size === 0) {
    return ["==", ["get", "事故内容"], "__none__"];
  }
  if (state.tyuya.size < ALL_TYUYA.length) {
    conditions.push([
      "in",
      ["slice", ["get", "昼夜"], 0, 1],
      ["literal", [...state.tyuya]],
    ]);
  }

  if (state.party && PARTY_CATEGORIES[state.party]) {
    conditions.push([
      "any",
      partyCondition("当事者種別（当事者A）", state.party),
      partyCondition("当事者種別（当事者B）", state.party),
    ]);
  }

  if (state.age) {
    conditions.push([
      "any",
      ["==", ["get", "年齢（当事者A）"], state.age],
      ["==", ["get", "年齢（当事者B）"], state.age],
    ]);
  }

  if (conditions.length === 0) {
    return ["boolean", true];
  }
  if (conditions.length === 1) {
    return conditions[0];
  }
  return ["all", ...conditions];
}
