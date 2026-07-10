import { cloudflareTest, readD1Migrations } from "@cloudflare/vitest-pool-workers";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [
    cloudflareTest(async () => ({
      wrangler: { configPath: "./wrangler.jsonc" },
      miniflare: {
        bindings: {
          DEPLOY_TOKEN_SHA256:
            "c23a45cfa237db77c09def37bfb4bfc7e263fd92bdbc6663021240f5f788f9b5",
          DOWNLOAD_HMAC_KEY_CURRENT: "test-download-hmac-key",
          DOWNLOAD_TOKEN_PREVIOUS_KEY_VERSION: "previous",
          DOWNLOAD_HMAC_KEY_PREVIOUS: "test-previous-download-hmac-key",
          TEST_MIGRATIONS: await readD1Migrations(
            fileURLToPath(new URL("../migrations", import.meta.url))
          )
        }
      }
    }))
  ],
  test: {
    setupFiles: ["./test/apply-migrations.ts"]
  }
});
