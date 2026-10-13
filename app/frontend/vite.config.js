import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The API runs on 8000. Proxying /api to it means the browser only ever talks to one
// origin, so there is no CORS to configure and no API address to hard-code anywhere.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
    },
  },
});
