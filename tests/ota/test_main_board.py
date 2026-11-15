import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("main_board", ROOT / "Tools/workflow/main_board.py")
BOARD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BOARD)
SHA = "a" * 40


class MainBoardTests(unittest.TestCase):
    def setUp(self):
        cache = ROOT / ".cache/main-board-tests"
        for parent in (cache, *cache.parents):
            if parent.exists() and (parent.is_symlink() or
                    getattr(parent.lstat(), "st_file_attributes", 0) & 0x400):
                raise RuntimeError("Redirected test output")
        cache.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=cache)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / ".git").mkdir()
        (self.root / "PLAN-OTA-EXEC.md").write_text("main board\n", encoding="utf-8")
        self.task = self.root / "task"
        self.task.mkdir()
        self.main = self.root
        self.pending = ""
        self.missing = False

    def query(self, cwd, *arguments):
        if arguments == ("rev-parse", "--path-format=absolute", "--git-common-dir"):
            return str(self.root / ".git")
        if arguments == ("worktree", "list", "--porcelain", "-z"):
            if self.missing:
                return ""
            return f"worktree {self.main}\0HEAD {SHA}\0branch refs/heads/main\0\0"
        if arguments == ("branch", "--show-current"):
            return "main" if Path(cwd) == self.root else "dev/flutter/example"
        if arguments == ("rev-parse", "HEAD"):
            return SHA
        if arguments[:1] == ("status",):
            return self.pending
        raise AssertionError(arguments)

    def inspect(self, remote=lambda _: SHA, caller=None):
        with patch.object(BOARD, "git", side_effect=self.query):
            return BOARD.inspect(caller or self.root, remote)

    def test_primary_main_is_current(self):
        result = self.inspect()
        self.assertTrue(result["ok"])
        self.assertEqual(result["delivery"], "MAIN_MATCHED")

    def test_task_copy_is_not_the_board(self):
        (self.task / "PLAN-OTA-EXEC.md").write_text("obsolete", encoding="utf-8")
        result = self.inspect(caller=self.task)
        self.assertEqual(result["board"], str(self.root / "PLAN-OTA-EXEC.md"))
        self.assertEqual(result["callerBranch"], "dev/flutter/example")

    def test_main_in_cache_is_rejected(self):
        self.main = self.task
        (self.task / "PLAN-OTA-EXEC.md").write_text("old entry", encoding="utf-8")
        self.assertIn("MAIN_NOT_AT_PRIMARY_ROOT", self.inspect()["errors"])

    def test_remote_advance_is_not_hidden_by_cached_main(self):
        result = self.inspect(lambda _: "b" * 40)
        self.assertFalse(result["ok"])
        self.assertIn("LOCAL_MAIN_NOT_CURRENT", result["errors"])

    def test_missing_main_binding_is_rejected(self):
        self.missing = True
        self.assertIn("MAIN_WORKTREE_MISSING_OR_AMBIGUOUS", self.inspect()["errors"])

    def test_local_draft_is_not_remote_delivery(self):
        self.pending = " M PLAN-OTA-EXEC.md"
        result = self.inspect()
        self.assertTrue(result["ok"])
        self.assertEqual(result["delivery"], "LOCAL_PENDING")

    def test_network_failure_is_not_current(self):
        def unavailable(_):
            raise subprocess.TimeoutExpired("git", 30)
        result = self.inspect(unavailable)
        self.assertFalse(result["remoteVerified"])
        self.assertEqual(result["localMain"], SHA)
        self.assertIn("REMOTE_MAIN_UNVERIFIED", result["errors"])

    def test_invalid_remote_response_is_rejected(self):
        self.assertFalse(self.inspect(lambda _: "main")["ok"])

    def test_null_delimited_worktree_names_preserve_spaces(self):
        self.assertEqual(BOARD.parse_worktrees("worktree D:/a b\0HEAD abc\0detached\0\0"),
                         [{"worktree": "D:/a b", "HEAD": "abc", "detached": ""}])


if __name__ == "__main__":
    unittest.main()
