import { useEffect, useState } from "react";

export type ThemeMode = "dark" | "light" | "system";
const KEY = "safestudy.theme";

function apply(mode: ThemeMode) {
  const dark = mode === "dark" || (mode === "system" && matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.classList.toggle("dark", dark);
}

export function useTheme(): [ThemeMode, (m: ThemeMode) => void] {
  const [mode, setMode] = useState<ThemeMode>(() => {
    try { return (localStorage.getItem(KEY) as ThemeMode) || "system"; } catch { return "system"; }
  });
  useEffect(() => {
    apply(mode);
    try { localStorage.setItem(KEY, mode); } catch { /* ignore */ }
    if (mode !== "system") return;
    const mq = matchMedia("(prefers-color-scheme: dark)");
    const on = () => apply("system");
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, [mode]);
  return [mode, setMode];
}
