import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./test",
  outputDir: process.env.PW_OUTPUT_DIR ?? "./.cache/ui-results",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: "line",
  use: {
    browserName: "chromium",
    headless: true,
    viewport: { width: 1440, height: 1000 },
    screenshot: "only-on-failure",
    trace: "off",
    launchOptions: { args: ["--disable-breakpad", "--disable-crash-reporter", "--disable-component-update"] }
  }
});
