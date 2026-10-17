export type Theme = "light" | "dark";

const KEY = "cfe-theme";

export function storedTheme(): Theme | null {
  try {
    const v = window.localStorage.getItem(KEY);
    return v === "light" || v === "dark" ? v : null;
  } catch {
    return null;
  }
}

export function systemTheme(): Theme {
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function currentTheme(): Theme {
  const attr = document.documentElement.getAttribute("data-theme");
  if (attr === "light" || attr === "dark") return attr;
  return storedTheme() ?? systemTheme();
}

export function applyTheme(theme: Theme): void {
  document.documentElement.setAttribute("data-theme", theme);
}

export function saveTheme(theme: Theme): void {
  try {
    window.localStorage.setItem(KEY, theme);
  } catch {
    // Storage unavailable: the choice holds for this page view only.
  }
}
