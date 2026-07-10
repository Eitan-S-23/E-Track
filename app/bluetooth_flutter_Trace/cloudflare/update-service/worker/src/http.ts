import { ApiError } from "./errors";
import { writeLog } from "./logger";

export function json(data: unknown, status = 200, headers?: HeadersInit): Response {
  return Response.json(data, {
    status,
    headers: {
      "Cache-Control": "no-store",
      ...headers
    }
  });
}

export function errorJson(error: unknown, requestId: string): Response {
  if (error instanceof ApiError) {
    return json(
      {
        errorCode: error.code,
        message: error.message,
        requestId
      },
      error.status
    );
  }

  const message = error instanceof Error ? error.message : String(error);
  writeLog("error", "unhandled_error", { requestId, error: message });
  return json(
    {
      errorCode: "BACKEND_UNAVAILABLE",
      message: "Update backend unavailable",
      requestId
    },
    503
  );
}

export function withRequestId(response: Response, requestId: string): Response {
  const headers = new Headers(response.headers);
  headers.set("X-Request-Id", requestId);
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers
  });
}

export function requestIdFrom(request: Request): string {
  return request.headers.get("X-Request-Id") ?? crypto.randomUUID();
}

export function clientIpFrom(request: Request): string {
  return (
    request.headers.get("CF-Connecting-IP") ??
    request.headers.get("X-Forwarded-For")?.split(",")[0]?.trim() ??
    "local"
  );
}
