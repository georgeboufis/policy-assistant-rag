import { createContext, useContext, useEffect, useState } from "react";

// Dark by default, light on request, remembered between visits. The choice is written
// onto <html data-theme>, which every colour token in styles.css keys off - so nothing
// in the components has to know which theme is showing.

const ThemeContext = createContext({ theme: "dark" });

export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(() => {
    try {
      return localStorage.getItem("ui-theme") === "light" ? "light" : "dark";
    } catch {
      return "dark";
    }
  });

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem("ui-theme", theme);
    } catch {
      /* the choice simply will not be remembered */
    }
  }, [theme]);

  return (
    <ThemeContext.Provider value={{ theme, setTheme }}>{children}</ThemeContext.Provider>
  );
}

export function useTheme() {
  return useContext(ThemeContext);
}
