import { handleAnnouncements } from "../../worker/src/announcements";
import { handleDownload } from "../../worker/src/downloads";
import { ApiError } from "../../worker/src/errors";
import { handleFirmwareDownload, handleFirmwareLatest } from "../../worker/src/firmware";
import { errorJson, json, requestIdFrom, withRequestId } from "../../worker/src/http";
import { handleLatest } from "../../worker/src/latest";
import { inventoryControl, reportInventory } from "../../worker/src/version_inventory";
import type { WorkerEnv } from "../../worker/src/types";

type PublicEnv = WorkerEnv;

export const onRequest: PagesFunction<PublicEnv> = async (context) => {
  const requestId = requestIdFrom(context.request);
  try {
    const response = await routePublicRequest(context, requestId);
    return withRequestId(response, requestId);
  } catch (error) {
    return withRequestId(errorJson(error, requestId), requestId);
  }
};

async function routePublicRequest(
  context: EventContext<PublicEnv, string, unknown>,
  requestId: string
): Promise<Response> {
  const url = new URL(context.request.url);
  const method = context.request.method.toUpperCase();

  if (method === "OPTIONS") {
    return new Response(null, { status: 204 });
  }

  // The catch-all function must explicitly hand known site assets back to Pages.
  if ((method === "GET" || method === "HEAD") &&
      ["/", "/index.html", "/favicon.ico", "/favicon.png", "/favicon.svg"].includes(url.pathname)) {
    return context.next();
  }

  if (method === "GET" && url.pathname === "/healthz") {
    return json({
      ok: true,
      service: "trace-update-public",
      environment: context.env.ENVIRONMENT
    });
  }

  if (method === "GET" && url.pathname === "/api/public/latest") {
    return handleLatest(context.request, context.env, requestId);
  }

  if (method === "GET" && url.pathname === "/api/public/announcements") {
    return handleAnnouncements(context.request, context.env, requestId);
  }

  if (method === "GET" && url.pathname === "/api/public/version-inventory/control") {
    return inventoryControl(context.request, context.env);
  }
  if (method === "POST" && url.pathname === "/api/public/version-inventory") {
    return reportInventory(context.request, context.env);
  }

  if (method === "GET" && url.pathname === "/api/public/firmware/latest") {
    return handleFirmwareLatest(context.request, context.env, requestId);
  }

  if (method === "GET" && url.pathname === "/api/public/download") {
    return handleDownload(context.request, context.env, requestId, "primary");
  }

  if (method === "GET" && url.pathname === "/api/public/firmware/download") {
    return handleFirmwareDownload(context.request, context.env, requestId);
  }

  if (method === "GET" && url.pathname === "/api/public/github-fallback") {
    return handleDownload(context.request, context.env, requestId, "github-fallback");
  }

  throw new ApiError("INVALID_PARAMETER", "Public route not found", 404);
}
