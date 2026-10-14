import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";

export default defineConfig({
  resolve: { alias: [
    { find: "cloudflare:workers", replacement: fileURLToPath(new URL("./host/platform.ts", import.meta.url)) },
    { find: "cloudflare:test", replacement: fileURLToPath(new URL("./host/platform.ts", import.meta.url)) }
  ] },
  test: { environment: "node", include: ["test/*.test.ts"], setupFiles: ["./test/apply-migrations.ts"],
    fileParallelism: false, maxWorkers: 1, reporters: ["verbose"] }
});
