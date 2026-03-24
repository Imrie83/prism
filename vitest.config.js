import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.js"],
    include: [
      "src/**/*.{test,spec}.{js,jsx}",
      "discover-service/**/*.{test,spec}.js",
      "screenshot-service/**/*.{test,spec}.js",
    ],
    coverage: {
      reporter: ["text", "html"],
      exclude: ["node_modules/", "src/test/", "**/node_modules/**"],
    },
  },
});