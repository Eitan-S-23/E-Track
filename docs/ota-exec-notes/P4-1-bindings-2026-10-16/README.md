# P4-1 Native Binding Qualification

Development observation from the single approved run `38859822756`, attempt 1,
at `c715ec6b00f8d9b06a820213da72421694b1e44c`. This archive is not a canonical
rehearsal, protected real-key build, production-zero-effect campaign or
independent acceptance bundle.

The original GitHub approval/run/job/artifact responses and log/artifact ZIPs
are retained byte-for-byte. `result.json` is the original ZIP member, not a
manually reconstructed result. `inspection.json` is a derived check against the
fixed existing synthetic fixture and actual step logs. The inspection scans ZIP
members for private credential values before archiving them.

The approved job used the shared native Wrangler runtime to read all three
existing test-bucket objects, verified the fixed Worker bindings, and observed
unchanged D1 counts and channel pointers. It requested no R2/D1 business writes;
Wrangler did create temporary remote-preview control-plane state. Completed job
and post-step logs are process-lifecycle evidence, not a separately measured
inventory of Cloudflare's ephemeral control-plane objects.

The additional configuration receipt records only the existing protected test
environment's missing registration-secret upload and metadata readback. It
does not approve a bootstrap descriptor, dispatch another job, unlock the gate,
change production configuration or expose any secret value.

For the remaining formal observations and exact next owner, use the existing
P4-1 task note and sole Spec. Preserve prior setup, readiness and bootstrap
archives unchanged. In particular, the old 3.2.7 raw base remains a byte source,
not proof that a device with its old development key can decrypt a real-key OTA.
