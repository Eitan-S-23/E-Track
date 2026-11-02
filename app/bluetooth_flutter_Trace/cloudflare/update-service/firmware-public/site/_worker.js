const publicPaths = new Set([
  "/healthz",
  "/api/public/firmware/latest",
  "/api/public/firmware/download"
]);

/** @type {ExportedHandler<Env>} */
const worker = {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method !== "GET" || !publicPaths.has(url.pathname)) {
      return Response.json({ errorCode: "NOT_FOUND", message: "Not found" }, { status: 404 });
    }
    try {
      // Preserve the public origin for signed download URLs, headers and streaming.
      return await env.FIRMWARE_SERVICE.fetch(request);
    } catch {
      console.error("FIRMWARE_PUBLIC_UPSTREAM_UNAVAILABLE");
      return Response.json({
        errorCode: "BACKEND_UNAVAILABLE",
        message: "Firmware service unavailable"
      }, { status: 503, headers: { "Cache-Control": "no-store" } });
    }
  }
};

export default worker;
