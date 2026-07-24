import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../pycapcut_gui/web_dist",
    emptyOutDir: true,
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes("node_modules/react/") || id.includes("node_modules/react-dom/")) {
            return "react";
          }
          if (id.includes("node_modules/zustand/") || id.includes("node_modules/immer/")) {
            return "state";
          }
          if (id.includes("node_modules/@radix-ui/")) {
            return "radix";
          }
        }
      }
    }
  },
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8765"
    }
  }
});
