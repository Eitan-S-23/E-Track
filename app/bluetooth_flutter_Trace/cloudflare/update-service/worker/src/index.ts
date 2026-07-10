import { Hono } from "hono";
import { handleAnnouncements } from "./announcements";
import { handleRegisterRelease } from "./ci";
import { ApiError } from "./errors";
import { errorJson, json, requestIdFrom, withRequestId } from "./http";
import { handleDownload } from "./downloads";
import {
  handleFirmwareDownload,
  handleFirmwareLatest,
  handleRegisterFirmwareRelease
} from "./firmware";
import { handleLatest } from "./latest";
import type { WorkerEnv } from "./types";

export { RateLimiter } from "./rate_limiter";

const app = new Hono<{ Bindings: WorkerEnv; Variables: { requestId: string } }>();

app.use("*", async (c, next) => {
  const requestId = requestIdFrom(c.req.raw);
  c.set("requestId", requestId);
  try {
    await next();
  } finally {
    c.res = withRequestId(c.res, requestId);
  }
});

app.get("/healthz", (c) =>
  json({
    ok: true,
    service: "trace-update-service",
    environment: c.env.ENVIRONMENT
  })
);

app.get("/api/public/latest", async (c) =>
  handleLatest(c.req.raw, c.env, c.get("requestId"))
);

app.get("/api/public/announcements", async (c) =>
  handleAnnouncements(c.req.raw, c.env, c.get("requestId"))
);

app.get("/api/public/firmware/latest", async (c) =>
  handleFirmwareLatest(c.req.raw, c.env, c.get("requestId"))
);

app.get("/api/public/download", async (c) =>
  handleDownload(c.req.raw, c.env, c.get("requestId"), "primary")
);

app.get("/api/public/firmware/download", async (c) =>
  handleFirmwareDownload(c.req.raw, c.env, c.get("requestId"))
);

app.get("/api/public/github-fallback", async (c) =>
  handleDownload(c.req.raw, c.env, c.get("requestId"), "github-fallback")
);

app.post("/api/ci/releases", async (c) =>
  handleRegisterRelease(c.req.raw, c.env, c.get("requestId"))
);

app.post("/api/ci/firmware/releases", async (c) =>
  handleRegisterFirmwareRelease(c.req.raw, c.env, c.get("requestId"))
);

app.all("/api/admin/*", () => {
  throw new ApiError(
    "BACKEND_UNAVAILABLE",
    "Direct Worker admin mutations are disabled; use the Access-protected Pages facade",
    503
  );
});

app.notFound(() => json({ errorCode: "NOT_FOUND", message: "Not found" }, 404));

app.onError((error, c) => errorJson(error, c.get("requestId") ?? crypto.randomUUID()));

export default {
  fetch: app.fetch
} satisfies ExportedHandler<WorkerEnv>;
