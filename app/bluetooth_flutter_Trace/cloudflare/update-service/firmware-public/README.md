# Firmware Test Public Access

This isolated Pages entry serves the existing `e-track-firmware-p41-test`
Worker through a service binding. It does not copy databases, storage, signing
keys or firmware business logic, and does not change the ordinary App update
service `trace-update-public-staging`.

Only GET `/healthz`, `/api/public/firmware/latest` and
`/api/public/firmware/download` are forwarded. All other routes and methods are
rejected before calling the Worker. Requests retain their public origin so the
existing Worker signs download URLs for the reachable Pages origin. Responses,
including download streams and rate-limit failures, are passed through unchanged.

The advanced-mode `site/_worker.js` is deployable JavaScript with no build step.
Use the installed Wrangler 4.105.0 and project-contained credentials/cache/logs:

    node --test test/worker.test.mjs
    wrangler types --include-runtime false worker-configuration.d.ts
    wrangler pages project create e-track-firmware-p41-public --production-branch main
    wrangler pages deploy site --project-name e-track-firmware-p41-public --branch main --no-bundle

Create the project only after confirming it is absent. A deployment remains a
test access route, not a production firmware/channel publication.

Before asking for an App update check, verify TLS and GET `/healthz` directly
from the phone's current network, then issue the actual latest request with all
required device/App identity parameters. Require HTTP 200 and schemaVersion 2;
`updateAvailable: false, errorCode: NO_UPDATE` is a successful check. A host
proxy, disabled certificate validation, forced DNS address or health response
alone does not establish phone firmware-query access. A future connection can
still fail after a successful preflight; report that failure rather than hiding it.

The installed App must be configured with this public origin before its own
query can use the repaired route. Deployment alone does not update an APK.
