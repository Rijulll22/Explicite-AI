const STORAGE_KEY = "explicite_appearance"

export interface AppearanceSettings {
  theme: string         // "Light (default)" | "Dark" | "System"
  codeFontSize: string  // "12px" | "13px" | "14px" | "16px"
  codeColorScheme: string // "Dark (default)" | "Light" | "High Contrast"
}

export const DEFAULT_APPEARANCE: AppearanceSettings = {
  theme: "Light (default)",
  codeFontSize: "13px",
  codeColorScheme: "Dark (default)",
}

export function loadAppearance(): AppearanceSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return { ...DEFAULT_APPEARANCE }
    return { ...DEFAULT_APPEARANCE, ...JSON.parse(raw) }
  } catch {
    return { ...DEFAULT_APPEARANCE }
  }
}

export function saveAppearance(s: AppearanceSettings): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(s))
  } catch { /* private window / storage full — silently ignore */ }
}

export function applyAppearance(s: AppearanceSettings): void {
  const root = document.documentElement

  // Theme
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches
  const dark = s.theme === "Dark" || (s.theme === "System" && prefersDark)
  root.setAttribute("data-theme", dark ? "dark" : "light")

  // Code font size — read by .code-block via CSS var
  root.style.setProperty("--code-font-size", s.codeFontSize)

  // Code colour scheme — class on root consumed by .code-block
  root.setAttribute("data-code-scheme", schemeClass(s.codeColorScheme))
}

function schemeClass(label: string): string {
  if (label === "Light") return "code-light"
  if (label === "High Contrast") return "code-hc"
  return "code-dark"
}
