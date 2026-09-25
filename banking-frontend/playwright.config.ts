import { defineConfig } from "@playwright/test";
import { existsSync } from "node:fs";
export default defineConfig({
  testDir: "./tests",
  timeout: 90000,
  expect: { timeout: 15000 },
  use: {
    baseURL: "http://127.0.0.1:3107", headless: true,
    channel: existsSync("C:/Program Files/Google/Chrome/Application/chrome.exe") ? "chrome" : undefined,
  },
  webServer: {
    command: "npm run dev -- --port 3107",
    url: "http://127.0.0.1:3107",
    reuseExistingServer: false,
    timeout: 180000,
  },
  reporter: "list",
});
