import { fileURLToPath } from "node:url";
import host from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/worker/test/vitest.host.config.ts";

const worker = fileURLToPath(new URL("../../app/bluetooth_flutter_Trace/cloudflare/update-service/worker/", import.meta.url));
export default {
  ...host,
  root: worker,
  resolve: { ...host.resolve, alias: [...host.resolve.alias,
    { find: "vitest", replacement: `${worker.replaceAll("\\", "/")}node_modules/vitest/dist/index.js` }] },
  test: { ...host.test,
    include: [fileURLToPath(new URL("../../tests/ota/firmware-pipeline.host.test.ts", import.meta.url)).replaceAll("\\", "/")] }
};
