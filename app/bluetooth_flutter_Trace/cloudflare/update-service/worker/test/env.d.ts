import type { WorkerEnv } from "../src/types";

declare module "cloudflare:test" {
  interface ProvidedEnv extends WorkerEnv {}
}

declare module "cloudflare:workers" {
  interface ProvidedEnv extends WorkerEnv {
    TEST_MIGRATIONS: import("cloudflare:test").D1Migration[];
  }
}

declare global {
  namespace Cloudflare {
    interface Env extends WorkerEnv {
      TEST_MIGRATIONS: import("cloudflare:test").D1Migration[];
    }
  }
}
