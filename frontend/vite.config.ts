import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The frontend never learns the backend's address. Everything goes to /api on the same
// origin and Vite proxies it in development, so no CORS configuration has to exist purely
// for local work — and production can put both behind one origin unchanged.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
