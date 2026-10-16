"""Audit selected evidence with opaque local credentials; print no credential values."""
import json
import os
import sys
import zipfile
from pathlib import Path

root = Path.cwd().resolve()
work = root / ".cache/p41-acceptance-20261016"
private = root / ".cache/cf-auth-input"
secrets = []
for name in ["token.txt", "p41-ci-token.txt"]:
    value = (private / name).read_text(encoding="utf8").strip()
    if value:
        secrets.append((name, value.encode()))
key = json.loads((private / "p41-rehearsal-ota-key.json").read_bytes())["keyHex"]
secrets.extend([("OTA_KEY_HEX", key.lower().encode()), ("OTA_KEY_HEX", key.upper().encode())])
deploy = json.loads((private / "firmware-test-secrets.json").read_bytes())["TRACE_DEPLOY_TOKEN"]
secrets.append(("TEST_DEPLOY_TOKEN", deploy.encode()))
if os.environ.get("P41_AUDIT_GITHUB_TOKEN"):
    secrets.append(("GITHUB_TOKEN", os.environ["P41_AUDIT_GITHUB_TOKEN"].encode()))
findings = []
files = members = 0


def inspect(name, data):
    for category, secret in secrets:
        if len(secret) >= 16 and secret in data:
            findings.append({"path": name, "category": category})


for folder in ["commands", "formal", "cloud", "review", "inputs", "github"]:
    for file in (work / folder).rglob("*"):
        if not file.is_file():
            continue
        file.resolve().relative_to(work)
        files += 1
        name = file.relative_to(work).as_posix()
        inspect(name, file.read_bytes())
        if file.suffix == ".zip":
            with zipfile.ZipFile(file) as archive:
                for entry in archive.namelist():
                    members += 1
                    if entry.endswith("private-key.h"):
                        findings.append({"path": name + ":" + entry, "category": "PRIVATE_KEY_HEADER"})
                    inspect(name + ":" + entry, archive.read(entry))
print(json.dumps({"ok": not findings, "files": files, "zip_members": members, "findings": findings,
                  "scope": "Opaque credential text/private-header audit; intended key-bound firmware binary remains a firmware artifact"}))
sys.exit(0 if not findings else 1)
