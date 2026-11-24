"""Initial QQ SMTP setup for the three existing E-Track targets.

No mail credentials in argv, files, environment variables or receipts. The
interactive owner enters them with getpass, and they go straight to Cloudflare.
This does not deploy Pages, send email, or enable required email verification.
"""
from __future__ import annotations

import argparse
import copy
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import getpass
import json
import os
from pathlib import Path
import re
import runpy
import ssl
import sys
import time
import urllib.error
import urllib.request
import uuid
import warnings

ROOT = Path(__file__).resolve().parents[2]
ACCOUNT = "af6dd848e6a21f1cd26d44b1b656af7b"
WORKER = "trace-update-service-staging"
PAGES = ("trace-update-public-staging", "trace-update-admin-staging")
WORKER_ROUTE = "/workers/scripts/" + WORKER
MAIL_KEYS = ("ACCOUNT_SMTP_USERNAME", "ACCOUNT_SMTP_AUTH_CODE", "ACCOUNT_MAIL_PROVIDER")
TOKEN_FILE = ".cache/p41-dev-20261015/.cache/cf-auth-input/p41-ci-token.txt"
PUBLIC_ORIGINS = (
    "https://trace-update-service-staging.tangjichentudou.workers.dev",
    "https://trace-update-public-staging.pages.dev",
)


class SetupError(RuntimeError):
    """Only fixed, non-secret messages may be exposed to the owner."""


def check(condition, message):
    if not condition:
        raise SetupError(message)


def checked_path(path):
    guard = runpy.run_path(str(ROOT / ".agents/skills/e-track-flutter-debug/scripts/host_io.py"))
    return guard["checked_output"](ROOT, path)


def prepare_host():
    check(Path.cwd().resolve() == ROOT, "Start from the project root.")
    check(sys.dont_write_bytecode and sys.flags.isolated and sys.flags.no_site,
          "Python must run with -I -S -B.")
    base = checked_path(ROOT / ".cache/account-mail-activation")
    base.mkdir(parents=True, exist_ok=True)
    for name in ("HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "TEMP", "TMP", "TMPDIR",
                 "XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME"):
        os.environ[name] = str(base)
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    for name in ("SSLKEYLOGFILE", "NODE_OPTIONS", "NODE_COMPILE_CACHE", "NODE_REDIRECT_WARNINGS"):
        os.environ.pop(name, None)
    return base


def read_cloud_token():
    """Reuse the registered CF-CI-01 file and existing SU owner-read route."""
    check(os.name == "nt", "This owner credential entry is Windows-only.")
    adv = ctypes.WinDLL("advapi32", use_last_error=True)
    adv.GetUserNameW.argtypes = [wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    name, length = ctypes.create_unicode_buffer(256), wintypes.DWORD(256)
    check(adv.GetUserNameW(name, ctypes.byref(length)), "Cannot identify credential owner.")
    path = ROOT / TOKEN_FILE
    if name.value.casefold() == "su":
        return path.read_text(encoding="utf-8").strip()
    check(name.value.casefold() == "system", "Run as the existing SU owner.")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    wts = ctypes.WinDLL("wtsapi32", use_last_error=True)
    kernel.WTSGetActiveConsoleSessionId.restype = wintypes.DWORD
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    wts.WTSQueryUserToken.argtypes = [wintypes.ULONG, ctypes.POINTER(wintypes.HANDLE)]
    adv.ImpersonateLoggedOnUser.argtypes = [wintypes.HANDLE]
    token = wintypes.HANDLE()
    check(wts.WTSQueryUserToken(kernel.WTSGetActiveConsoleSessionId(), ctypes.byref(token)),
          "Existing console credential owner is unavailable.")
    active = False
    try:
        check(adv.ImpersonateLoggedOnUser(token), "Cannot enter existing credential owner.")
        active = True
        length.value = 256
        check(adv.GetUserNameW(name, ctypes.byref(length)) and name.value.casefold() == "su",
              "Expected existing SU console owner.")
        return path.read_text(encoding="utf-8").strip()
    finally:
        if active and not adv.RevertToSelf():
            # Do not continue operating under an unintended token.
            kernel.CloseHandle(token)
            raise SetupError("Credential owner cleanup failed.")
        kernel.CloseHandle(token)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise SetupError("Redirect refused; no credentials forwarded.")


def validate_request(method, route, body):
    reads = {WORKER_ROUTE + "/settings", WORKER_ROUTE + "/secrets"}
    reads.update("/pages/projects/" + p for p in PAGES)
    if method == "GET":
        check(route in reads and body is None, "Read outside setup scope.")
    elif method == "PUT":
        check(route == WORKER_ROUTE + "/secrets" and isinstance(body, dict), "Write outside Worker scope.")
        check(set(body) == {"name", "text", "type"} and body["name"] in MAIL_KEYS
              and body["type"] == "secret_text", "Only the three mail secrets may change.")
    elif method == "PATCH":
        check(route in {"/pages/projects/" + p for p in PAGES} and isinstance(body, dict),
              "Write outside Pages scope.")
        check(set(body) == {"deployment_configs"} and set(body["deployment_configs"]) == {"production"},
              "Only Pages Production may change.")
        config = body["deployment_configs"]["production"]
        check(set(config) <= {"env_vars", "wrangler_config_hash"} and "env_vars" in config,
              "Only mail settings may change.")
        check(set(config["env_vars"]) == set(MAIL_KEYS), "Only the three mail secrets may change.")
        check(all(set(v) == {"type", "value"} and v["type"] == "secret_text"
                  for v in config["env_vars"].values()), "Mail settings must be encrypted secrets.")
    else:
        raise SetupError("HTTP method outside setup scope.")


class CloudAPI:
    def __init__(self, token):
        check(bool(token) and not re.search(r"\s", token), "Registered Cloudflare input is invalid.")
        self.token = token
        # Same bounded local proxy as the existing deployment/readback adapters.
        self.opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({"https": "http://127.0.0.1:7897"}),
            urllib.request.HTTPSHandler(context=ssl.create_default_context()), NoRedirect())
        self.deadline = time.monotonic() + 240

    def request(self, url, body=None, *, method="GET", authenticated=False):
        remaining = self.deadline - time.monotonic()
        check(remaining > 0, "Setup request deadline reached; no automatic retry.")
        headers = {"Accept": "application/json", "User-Agent": "E-Track-Mail-Setup"}
        if authenticated:
            headers["Authorization"] = "Bearer " + self.token
        data = None if body is None else json.dumps(body).encode("utf-8")
        if data is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with self.opener.open(req, timeout=min(25, remaining)) as response:
                raw = response.read(2 * 1024 * 1024 + 1)
                check(len(raw) <= 2 * 1024 * 1024, "Response limit exceeded.")
                value = json.loads(raw)
        except urllib.error.HTTPError as error:
            status = error.code
            error.close()
            raise SetupError("Cloud request HTTP " + str(status) + "; no automatic retry.") from None
        except SetupError:
            raise
        except Exception:
            raise SetupError("Cloud request failed; result may be unknown. No automatic retry.") from None
        if authenticated:
            check(isinstance(value, dict) and value.get("success") is True, "Cloudflare rejected the request.")
            return value.get("result")
        return value

    def call(self, method, route, body=None):
        validate_request(method, route, body)
        return self.request("https://api.cloudflare.com/client/v4/accounts/" + ACCOUNT + route,
                            body, method=method, authenticated=True)

    def public_status(self, origin):
        check(origin in PUBLIC_ORIGINS, "Unknown public origin.")
        return self.request(origin + "/api/auth/status")


def snapshot(api):
    worker = api.call("GET", WORKER_ROUTE + "/settings")
    check(isinstance(worker, dict) and isinstance(worker.get("bindings"), list), "Worker metadata is incomplete.")
    bindings = {b["name"]: b for b in worker["bindings"]}
    check(bindings.get("DB", {}).get("id") == "0133ad9e-d4a2-4fef-a659-4f2bf3d3a645",
          "Worker database identity differs; stopped.")
    check(bindings.get("ENVIRONMENT", {}).get("text") == "staging", "Wrong Worker environment.")
    pages = {}
    for project in PAGES:
        value = api.call("GET", "/pages/projects/" + project)
        check(value.get("name") == project and value.get("production_branch") == "main", "Wrong Pages target.")
        check(set(value.get("deployment_configs", {})) >= {"production", "preview"}, "Pages environments missing.")
        pages[project] = value
    return {"worker": worker, "pages": pages}


def mail_presence(state):
    entries = {WORKER: {b["name"]: b for b in state["worker"]["bindings"]}}
    entries.update({p: value["deployment_configs"]["production"].get("env_vars", {})
                    for p, value in state["pages"].items()})
    return {target: {key: entries[target].get(key, {}).get("type") == "secret_text" for key in MAIL_KEYS}
            for target in entries}


def assert_initial_setup(state):
    entries = [b["name"] for b in state["worker"]["bindings"]]
    for value in state["pages"].values():
        entries.extend(value["deployment_configs"]["production"].get("env_vars", {}))
    # A provider-only selection does not contain mailbox credentials. The owner
    # may have entered it while following the earlier dashboard instructions.
    check(not set(entries).intersection(MAIL_KEYS[:2]),
          "Mailbox credentials already exist, possibly from a partial run. Ask the agent to reconcile; do not overwrite.")


def without_mail(state):
    value = copy.deepcopy(state)
    worker = value["worker"]
    worker["bindings"] = sorted((b for b in worker["bindings"] if b["name"] not in MAIL_KEYS), key=lambda b: b["name"])
    # Secret changes can update deployment annotations, not runtime bindings.
    for key in ("workers/tag", "workers/message", "workers/triggered_by"):
        worker.get("annotations", {}).pop(key, None)
    for project, page in value["pages"].items():
        configs = page["deployment_configs"]
        for name in MAIL_KEYS:
            configs["production"].get("env_vars", {}).pop(name, None)
        value["pages"][project] = {
            key: page.get(key) for key in ("name", "id", "production_branch", "deployment_configs",
                                          "source", "build_config", "domains", "canonical_deployment")}
    return value


def validate_mailbox(sender, code):
    check(isinstance(sender, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.+-]{0,63}@(qq|foxmail)\.com", sender) is not None,
          "Enter the full QQ/Foxmail address belonging to this authorization code.")
    check(isinstance(code, str) and re.fullmatch(r"[A-Za-z]{16}", code) is not None,
          "Enter the 16-letter SMTP authorization code, not the mailbox password.")


def configure(api, before, sender, code, event):
    validate_mailbox(sender, code)
    assert_initial_setup(before)
    values = dict(zip(MAIL_KEYS, (sender, code, "qq-smtp")))
    # Provider last prevents the Worker selecting SMTP with missing credentials.
    for name in MAIL_KEYS:
        event("write_started", WORKER, name)
        api.call("PUT", WORKER_ROUTE + "/secrets", {"name": name, "text": values[name], "type": "secret_text"})
        event("write_accepted", WORKER, name)
    for project in PAGES:
        production = before["pages"][project]["deployment_configs"]["production"]
        config = {"env_vars": {k: {"type": "secret_text", "value": v} for k, v in values.items()}}
        if "wrangler_config_hash" in production:
            config["wrangler_config_hash"] = production["wrangler_config_hash"]
        event("write_started", project, "mail_settings")
        api.call("PATCH", "/pages/projects/" + project, {"deployment_configs": {"production": config}})
        event("write_accepted", project, "mail_settings")
    after = snapshot(api)
    check(all(all(fields.values()) for fields in mail_presence(after).values()), "Secret metadata readback incomplete.")
    check(without_mail(before) == without_mail(after), "Unrelated configuration changed; agent review required.")
    event("verified", "all_targets", "mail_settings_only")
    return after


def prompt_mailbox():
    check(sys.stdin.isatty(), "Use the local interactive launcher; piped secrets are not accepted.")
    sender = input("Sender mailbox (full @qq.com or @foxmail.com address): ").strip()
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        code = getpass.getpass("NEW SMTP authorization code (input is hidden): ").strip()
    validate_mailbox(sender, code)
    return sender, code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Read-only cloud preflight; no mailbox input")
    parser.add_argument("--configure", action="store_true", help="Interactive initial mail-secret configuration")
    args = parser.parse_args()
    check(args.check != args.configure, "Choose exactly one of --check or --configure.")
    base = prepare_host()
    out = checked_path(base / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]))
    out.mkdir()
    receipt = checked_path(out / "result.json")
    pending = checked_path(out / "result.tmp")
    result = {"ok": False, "mode": "check" if args.check else "configure", "events": [],
              "mailSent": False, "pagesDeployed": False, "emailVerificationEnabledByTool": False}

    def save():
        with pending.open("w", encoding="utf-8") as stream:
            json.dump(result, stream, indent=2)
            stream.write("\n")
        os.replace(pending, receipt)

    def event(stage, target, setting):
        result["events"].append({"stage": stage, "target": target, "setting": setting,
                                 "at": datetime.now(timezone.utc).isoformat()})
        save()
        print(stage + ": " + target + " / " + setting, flush=True)

    # OS-owned lock is released on exit/crash; never delete another process's lock.
    import msvcrt
    lock_path = checked_path(base / "setup.lock")
    lock = lock_path.open("a+b")
    locked = False
    try:
        if lock.seek(0, 2) == 0:
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        locked = True
        print("Checking the three existing Cloudflare targets...", flush=True)
        api = CloudAPI(read_cloud_token())
        before = snapshot(api)
        result["mailSecretPresence"] = mail_presence(before)
        result["publicReadiness"] = {}
        for origin in PUBLIC_ORIGINS:
            status = api.public_status(origin)
            result["publicReadiness"][origin] = {k: status.get(k) for k in (
                "registrationEnabled", "emailVerificationEnabled", "emailDeliveryAvailable", "passwordResetAvailable",
                "automaticDailyLimit", "manualDailyLimit")}
        save()
        assert_initial_setup(before)
        check(all(v.get("emailDeliveryAvailable") is False and v.get("emailVerificationEnabled") is False
                  for v in result["publicReadiness"].values()), "Mail is already active or readiness is unknown; reconcile first.")
        result["readyForInitialSetup"] = True
        if args.configure:
            print("No mailbox password. Use a fresh SMTP authorization code. Nothing is stored locally.", flush=True)
            sender, code = prompt_mailbox()
            # Do not hold a stale snapshot while waiting for interactive input.
            api.deadline = time.monotonic() + 240
            current = snapshot(api)
            check(current == before, "Cloud settings changed during input; no write performed.")
            after = configure(api, current, sender, code, event)
            sender = code = ""
            result["mailSecretPresence"] = mail_presence(after)
            result["state"] = "SECRETS_CONFIGURED_PAGES_ACTIVATION_AND_REAL_MAIL_PENDING"
            print("Secrets configured. Tell the agent: configured. Pages activation and a real email test remain.", flush=True)
        else:
            result["state"] = "READ_ONLY_PREFLIGHT_COMPLETE"
            print("Preflight passed. No cloud settings were changed.", flush=True)
        result["ok"] = True
    except (Exception, KeyboardInterrupt) as error:
        result["error"] = str(error) if type(error) is SetupError else "Setup stopped (" + type(error).__name__ + ")."
        result["state"] = "STOPPED_NO_AUTOMATIC_RETRY"
        print(result["error"], flush=True)
    finally:
        if locked:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
        lock.close()
        save()
        print("Receipt: " + str(receipt), flush=True)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SetupError as error:
        print(str(error))
        raise SystemExit(1) from None
