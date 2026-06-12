import { useEffect, useState } from "react";

const STORAGE_KEY = "scrapegpt-theme";

export function useTheme() {
  const [dark, setDark] = useState<boolean>(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) return stored === "dark";
      return window.matchMedia("(prefers-color-scheme: dark)").matches;
    } catch {
      return false;
    }
  });

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    try {
      localStorage.setItem(STORAGE_KEY, dark ? "dark" : "light");
    } catch {
      // ignore storage errors
    }
  }, [dark]);

  return { dark, toggle: () => setDark((d) => !d) };
}
