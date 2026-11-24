"""Offline scope/safety tests. No Cloudflare or SMTP network requests."""
import copy
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import uuid

SOURCE = Path(__file__).with_name("configure_account_mail.py")
spec = importlib.util.spec_from_file_location("mail_setup", SOURCE)
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)
CODE = "abcdefghijklmnop"
SENDER = "synthetic-test@foxmail.com"


def state():
    return {
        "worker": {"bindings": [
            {"name": "DB", "type": "d1", "id": "0133ad9e-d4a2-4fef-a659-4f2bf3d3a645"},
            {"name": "ENVIRONMENT", "type": "plain_text", "text": "staging"},
            {"name": "KEEP_SECRET", "type": "secret_text"}], "tags": ["cf:environment=staging"]},
        "pages": {p: {"name": p, "id": p, "production_branch": "main",
                       "canonical_deployment": {"id": "unchanged"},
                       "deployment_configs": {
                           "production": {"wrangler_config_hash": "preserved", "env_vars": {
                               "KEEP_SECRET": {"type": "secret_text"},
                               "APP_ID": {"type": "plain_text", "value": "trace"}}},
                           "preview": {"env_vars": {"PRIVATE": {"type": "secret_text"}}}}}
                  for p in setup.PAGES},
    }


class FakeAPI:
    def __init__(self, value=None, fail_write=None, mutate_unrelated=False):
        self.value = copy.deepcopy(value or state())
        self.calls = []
        self.writes = 0
        self.fail_write = fail_write
        self.mutate_unrelated = mutate_unrelated

    def call(self, method, route, body=None):
        setup.validate_request(method, route, body)
        self.calls.append((method, route, copy.deepcopy(body)))
        if method == "GET":
            if route == setup.WORKER_ROUTE + "/settings":
                return copy.deepcopy(self.value["worker"])
            return copy.deepcopy(self.value["pages"][route.split("/")[-1]])
        self.writes += 1
        if self.writes == self.fail_write:
            raise setup.SetupError("Synthetic unknown write result.")
        if method == "PUT":
            self.value["worker"]["bindings"] = [b for b in self.value["worker"]["bindings"] if b["name"] != body["name"]]
            self.value["worker"]["bindings"].append({"name": body["name"], "type": "secret_text"})
        else:
            self.value["pages"][route.split("/")[-1]]["deployment_configs"]["production"]["env_vars"].update(
                {k: {"type": v["type"]} for k, v in body["deployment_configs"]["production"]["env_vars"].items()})
        if self.mutate_unrelated:
            self.value["worker"]["tags"] = ["unexpected"]


class MailSetupTests(unittest.TestCase):
    def test_read_only_preflight_makes_three_exact_gets(self):
        api = FakeAPI()
        self.assertEqual(setup.snapshot(api), state())
        self.assertEqual([c[0] for c in api.calls], ["GET"] * 3)

    def test_wrong_database_stops_before_pages(self):
        value = state()
        value["worker"]["bindings"][0]["id"] = "other"
        api = FakeAPI(value)
        with self.assertRaises(setup.SetupError):
            setup.snapshot(api)
        self.assertEqual(len(api.calls), 1)

    def test_wrong_worker_environment(self):
        value = state()
        value["worker"]["bindings"][1]["text"] = "production"
        with self.assertRaises(setup.SetupError):
            setup.snapshot(FakeAPI(value))

    def test_wrong_pages_branch(self):
        value = state()
        value["pages"][setup.PAGES[0]]["production_branch"] = "other"
        with self.assertRaises(setup.SetupError):
            setup.snapshot(FakeAPI(value))

    def test_missing_preview_stops(self):
        value = state()
        del value["pages"][setup.PAGES[0]]["deployment_configs"]["preview"]
        with self.assertRaises(setup.SetupError):
            setup.snapshot(FakeAPI(value))

    def test_mailbox_validates(self):
        setup.validate_mailbox(SENDER, CODE)
        setup.validate_mailbox("123456@qq.com", CODE)

    def test_mailbox_rejects_injection_and_other_domains(self):
        for sender in ("user@gmail.com", "user@qq.com\r\nBcc:x", "User <x@qq.com>", "x@qq.com.evil"):
            with self.subTest(sender=sender), self.assertRaises(setup.SetupError):
                setup.validate_mailbox(sender, CODE)

    def test_code_rejects_password_whitespace_and_wrong_length(self):
        for code in ("", "0123456789012345", CODE + "\n", CODE + "a", "a b c"):
            with self.subTest(length=len(code)), self.assertRaises(setup.SetupError):
                setup.validate_mailbox(SENDER, code)

    def test_invalid_mailbox_never_writes(self):
        api = FakeAPI()
        with self.assertRaises(setup.SetupError):
            setup.configure(api, state(), "invalid", CODE, lambda *a: None)
        self.assertFalse(api.calls)

    def test_initial_only_rejects_partial_worker_setup(self):
        value = state()
        value["worker"]["bindings"].append({"name": setup.MAIL_KEYS[0], "type": "plain_text"})
        api = FakeAPI(value)
        with self.assertRaises(setup.SetupError):
            setup.configure(api, value, SENDER, CODE, lambda *a: None)
        self.assertEqual(api.writes, 0)

    def test_initial_only_rejects_partial_pages_setup(self):
        value = state()
        value["pages"][setup.PAGES[1]]["deployment_configs"]["production"]["env_vars"][setup.MAIL_KEYS[1]] = {}
        with self.assertRaises(setup.SetupError):
            setup.assert_initial_setup(value)

    def test_provider_only_dashboard_preparation_can_be_completed(self):
        value = state()
        value["worker"]["bindings"].append({"name": setup.MAIL_KEYS[2], "type": "secret_text"})
        for page in value["pages"].values():
            page["deployment_configs"]["production"]["env_vars"][setup.MAIL_KEYS[2]] = {"type": "secret_text"}
        api = FakeAPI(value)
        after = setup.configure(api, value, SENDER, CODE, lambda *a: None)
        self.assertEqual(api.writes, 5)
        self.assertEqual(sum(b["name"] == setup.MAIL_KEYS[2] for b in after["worker"]["bindings"]), 1)
        self.assertEqual(setup.without_mail(value), setup.without_mail(after))

    def test_worker_non_mail_secret_write_refused(self):
        with self.assertRaises(setup.SetupError):
            setup.validate_request("PUT", setup.WORKER_ROUTE + "/secrets",
                                   {"name": "ACCESS_SECRET", "type": "secret_text", "text": "synthetic"})

    def test_pages_non_mail_secret_write_refused(self):
        bindings = {k: {"type": "secret_text", "value": "synthetic"} for k in setup.MAIL_KEYS}
        bindings["ACCESS_SECRET"] = {"type": "secret_text", "value": "synthetic"}
        with self.assertRaises(setup.SetupError):
            setup.validate_request("PATCH", "/pages/projects/" + setup.PAGES[0],
                                   {"deployment_configs": {"production": {"env_vars": bindings}}})

    def test_hidden_input_warning_stops_instead_of_echoing(self):
        from types import SimpleNamespace
        import warnings
        def unsafe_fallback(*args):
            warnings.warn("Synthetic echo fallback", setup.getpass.GetPassWarning)
            self.fail("A getpass fallback must not reach a visible input call")
        with patch.object(sys, "stdin", SimpleNamespace(isatty=lambda: True)), \
                patch("builtins.input", return_value=SENDER), \
                patch.object(setup.getpass, "getpass", side_effect=unsafe_fallback), \
                self.assertRaises(setup.getpass.GetPassWarning):
            setup.prompt_mailbox()

    def test_mail_presence_requires_encrypted_metadata(self):
        value = state()
        value["worker"]["bindings"].append({"name": setup.MAIL_KEYS[0], "type": "plain_text"})
        self.assertFalse(setup.mail_presence(value)[setup.WORKER][setup.MAIL_KEYS[0]])

    def test_success_changes_only_three_mail_secrets_per_target(self):
        api, events = FakeAPI(), []
        before = state()
        after = setup.configure(api, before, SENDER, CODE, lambda *args: events.append(args))
        self.assertEqual(api.writes, 5)
        self.assertEqual([c[2]["name"] for c in api.calls[:3]], list(setup.MAIL_KEYS))
        self.assertEqual(api.calls[2][2]["text"], "qq-smtp")
        self.assertEqual(setup.without_mail(before), setup.without_mail(after))
        self.assertEqual(before, state())
        for call in api.calls[3:5]:
            config = call[2]["deployment_configs"]
            self.assertEqual(set(config), {"production"})
            self.assertEqual(config["production"]["wrangler_config_hash"], "preserved")
        self.assertTrue(all(all(v.values()) for v in setup.mail_presence(after).values()))
        self.assertNotIn(CODE, json.dumps(events))
        self.assertNotIn(SENDER, json.dumps(events))
        self.assertEqual(events[-1], ("verified", "all_targets", "mail_settings_only"))

    def test_failed_or_uncertain_write_never_retries(self):
        for count in range(1, 6):
            api, events = FakeAPI(fail_write=count), []
            with self.subTest(count=count), self.assertRaises(setup.SetupError):
                setup.configure(api, state(), SENDER, CODE, lambda *args: events.append(args))
            self.assertEqual(api.writes, count)
            self.assertEqual(events[-1][0], "write_started")
            self.assertNotIn(CODE, json.dumps(events))

    def test_unrelated_change_is_not_accepted_as_success(self):
        with self.assertRaisesRegex(setup.SetupError, "Unrelated configuration"):
            setup.configure(FakeAPI(mutate_unrelated=True), state(), SENDER, CODE, lambda *a: None)

    def test_preview_change_detected_even_for_mail_key(self):
        before, after = state(), state()
        after["pages"][setup.PAGES[0]]["deployment_configs"]["preview"]["env_vars"][setup.MAIL_KEYS[0]] = {}
        self.assertNotEqual(setup.without_mail(before), setup.without_mail(after))

    def test_foreign_routes_and_delete_refused(self):
        for method, route in (("GET", "/accounts"), ("DELETE", setup.WORKER_ROUTE + "/secrets"),
                              ("PUT", "/workers/scripts/other/secrets"), ("PATCH", "/pages/projects/new")):
            with self.subTest(method=method), self.assertRaises(setup.SetupError):
                setup.validate_request(method, route, {})

    def test_preview_and_plaintext_payloads_refused(self):
        for env in ("preview", "production"):
            body = {"deployment_configs": {env: {"env_vars": {k: {"type": "plain_text", "value": "x"}
                                                                     for k in setup.MAIL_KEYS}}}}
            with self.assertRaises(setup.SetupError):
                setup.validate_request("PATCH", "/pages/projects/" + setup.PAGES[0], body)

    def test_redirect_never_forwards_credentials(self):
        with self.assertRaises(setup.SetupError):
            setup.NoRedirect().redirect_request(None, None, 302, "", {}, "https://other.invalid")

    def test_noninteractive_input_refused(self):
        with patch.object(sys, "stdin", io.StringIO("not-a-secret")), self.assertRaises(setup.SetupError):
            setup.prompt_mailbox()

    def test_hidden_input_no_fallback_echo(self):
        from types import SimpleNamespace
        with patch.object(sys, "stdin", SimpleNamespace(isatty=lambda: True)), \
                patch("builtins.input", return_value=SENDER), \
                patch.object(setup.getpass, "getpass", return_value=CODE):
            self.assertEqual(setup.prompt_mailbox(), (SENDER, CODE))

    def test_boundaries_reject_project_sibling(self):
        with self.assertRaises(ValueError):
            setup.checked_path(setup.ROOT.parent / "E-Track-other" / "out.json")


if __name__ == "__main__":
    base = setup.prepare_host()
    output = io.StringIO()
    result = unittest.TextTestRunner(stream=output, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(MailSetupTests))
    transcript = output.getvalue()
    print(transcript)
    target = setup.checked_path(base / ("selftest-" + uuid.uuid4().hex[:8] + ".txt"))
    target.write_text(transcript, encoding="utf-8")
    print("Evidence: " + str(target))
    raise SystemExit(0 if result.wasSuccessful() else 1)
