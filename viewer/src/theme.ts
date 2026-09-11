export type Theme = "light" | "dark";

const STORAGE_KEY = "japan-legal-speed-30kmh-map-theme";

function systemPref(): Theme {
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function initialTheme(): Theme {
  let saved: string | null = null;
  try {
    saved = localStorage.getItem(STORAGE_KEY);
  } catch {
    /* プライベートモード等 */
  }
  return saved === "light" || saved === "dark" ? saved : systemPref();
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
