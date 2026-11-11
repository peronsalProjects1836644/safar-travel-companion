import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import path from "node:path";
import { defineConfig } from "vite";

// In development the API runs on :8010 (set API_URL to use another port). The proxy makes requests same-origin, so no CORS setup is needed locally.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
  server: {
    port: 5173,
    proxy: {
      "/api": { target: process.env.API_URL ?? "http://127.0.0.1:8010", changeOrigin: true, ws: true },
    },
  },
  build: {
    target: "es2020",
    rollupOptions: {
      output: {
        manualChunks: {
          react: ["react", "react-dom", "react-router-dom"],
          query: ["@tanstack/react-query"],
          map: ["leaflet"],
        },
      },
    },
  },
});
