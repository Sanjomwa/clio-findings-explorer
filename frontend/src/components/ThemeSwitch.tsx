import { useState } from "react";
import { applyTheme, currentTheme, saveTheme, type Theme } from "../theme";

export default function ThemeSwitch() {
  const [theme, setTheme] = useState<Theme>(currentTheme);

  function choose(next: Theme) {
    applyTheme(next);
    saveTheme(next);
    setTheme(next);
  }

  return (
    <div className="theme" role="group" aria-label="Colour theme">
      <button type="button" aria-pressed={theme === "light"} onClick={() => choose("light")}>
        Light
      </button>
      <button type="button" aria-pressed={theme === "dark"} onClick={() => choose("dark")}>
        Dark
      </button>
    </div>
  );
}
