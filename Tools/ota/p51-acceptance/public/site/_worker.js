const paths = new Set([
  "/api/public/firmware/latest",
  "/api/public/firmware/download"
]);

function unavailable() {
  return Response.json({
    errorCode: "BACKEND_UNAVAILABLE",
    message: "Benchmark firmware service unavailable"
  }, { status: 503, headers: { "Cache-Control": "no-store" } });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method !== "GET" || !paths.has(url.pathname)) {
      return Response.json({ errorCode: "NOT_FOUND", message: "Not found" }, {
        status: 404, headers: { "Cache-Control": "no-store" }
      });
    }
    try {
      const origin = env.P51_UPSTREAM_ORIGIN;
      if (typeof origin !== "string" ||
          !/^https:\/\/[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.trycloudflare\.com$/.test(origin) ||
          new URL(origin).origin !== origin) {
        return unavailable();
      }
      const headers = new Headers();
      for (const name of ["Accept", "Range", "If-Range"]) {
        if (request.headers.has(name)) headers.set(name, request.headers.get(name));
      }
      // Do not decode/re-encode signed or duplicate query parameters.
      const upstream = new Request(origin + url.pathname + url.search, {
        method: "GET", headers, redirect: "manual", signal: request.signal
      });
      const response = await fetch(upstream);
      if (response.status >= 300 && response.status < 400) {
        await response.body?.cancel();
        return unavailable();
      }
      return response;
    } catch {
      // Connection details and signed URLs must not appear in logs or errors.
      return unavailable();
    }
  }
};
