export type Theme = "light" | "dark";

const STORAGE_KEY = "japan-legal-speed-30kmh-map-theme";

/** 既定はダーク(判定の色が地図の上で見分けやすい)。index.html の data-theme と合わせる。 */
const DEFAULT_THEME: Theme = "dark";

export function initialTheme(): Theme {
  let saved: string | null = null;
  try {
    saved = localStorage.getItem(STORAGE_KEY);
  } catch {
    /* プライベートモード等 */
  }
  // 一度でも切り替えたらその選択を使う。無ければ OS 設定に関係なくダーク
  return saved === "light" || saved === "dark" ? saved : DEFAULT_THEME;
}

/** <html data-theme="…"> を更新して現在テーマを保存する。 */
export function applyThemeAttr(theme: Theme): void {
  document.documentElement.dataset.theme = theme;
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    /* 保存できなくても表示はできる */
  }
}
