import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import { LanguageProvider } from "./i18n.jsx";
import { ThemeProvider } from "./theme.jsx";
import "./styles.css";

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <ThemeProvider>
      <LanguageProvider>
        <App />
      </LanguageProvider>
    </ThemeProvider>
  </React.StrictMode>
);
