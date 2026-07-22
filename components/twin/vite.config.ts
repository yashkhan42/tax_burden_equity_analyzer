import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Streamlit serves a component's build directory as static files from an
// arbitrary mount path, so every asset reference must be relative — an
// absolute "/assets/..." resolves against the Streamlit host and 404s.
export default defineConfig({
  plugins: [react()],
  base: "./",
  build: { outDir: "build", emptyOutDir: true },
  server: { port: 5174, strictPort: true, cors: true },
});
