"""Guard the approved non-power sequencing exception without waiving product gates."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]


class NonPowerSequenceTests(unittest.TestCase):
    def read(self, path):
        return (ROOT / path).read_text(encoding="utf8")

    def test_decision_is_explicit_and_authorized(self):
        text = self.read("docs/ota-spec-decisions.md")
        section = text.split("## OTA-DEC-018 ", 1)[1].split("## \u7528\u6237\u88c1\u5b9a\u539f\u6587", 1)[0]
        for marker in ("DECIDED", "\u8bb0\u5f55 18", "14 \u9879", "03/05/07/15/16/17",
                       "AUTO \u539f\u4ef6", "\u751f\u4ea7\u664b\u5347", "\u4e0d\u65b0\u589e Git"):
            self.assertIn(marker, section)
        self.assertIn("### \u8bb0\u5f55 18", text)
        self.assertIn("> \u505a\u5427", text.split("### \u8bb0\u5f55 18", 1)[1])

    def test_all_consumers_reference_same_exception(self):
        for path in ("PLAN-OTA-EXEC.md", "docs/ota-cross-system-contracts.md",
                     "docs/ota-prompts/prompt-P5-1-acceptance.md",
                     "docs/ota-prompts/prompt-P5-2-acceptance.md",
                     "docs/ota-prompts/prompt-P5-3-acceptance.md"):
            with self.subTest(path=path):
                self.assertIn("OTA-DEC-018", self.read(path))

    def test_original_twenty_rows_and_physical_classes_remain(self):
        rows = re.findall(r"(?m)^\| (\d{2}) \| (AUTO|PHYSICAL) \|",
                          self.read("docs/ota-exec-notes/P1-6-implementation-evidence-2026-07-29.md"))
        self.assertEqual(len(rows), 20)
        self.assertEqual([key for key, kind in rows if kind == "PHYSICAL"], ["03", "05", "07", "15", "16", "17"])
        self.assertEqual(sum(kind == "AUTO" for _, kind in rows), 14)

    def test_current_readiness_does_not_silently_open(self):
        board = self.read("PLAN-OTA-EXEC.md")
        for task in ("P5-1", "P5-2"):
            row = next(line for line in board.splitlines() if re.match(r"\| \d+ \| " + task + r" \|", line))
            self.assertIn("P1-6 AUTO", row)
            self.assertIn("NOT_DISPATCHABLE", row)
            self.assertIn("BLOCKED_BY_DEPENDENCY", row)
        self.assertRegex(board, r"\| P1 \| bootloader \| \u8fdb\u884c\u4e2d \| 6/7 \|")

    def test_p51_numeric_gates_are_not_reduced(self):
        text = self.read("docs/ota-prompts/prompt-P5-1-acceptance.md")
        for marker in ("SD/BLE \u00d7 full/patch", "30/30", "\u56db\u5c0f\u65f6\u4e0d\u53ef\u6062\u590d\u9519\u8bef\u6570\u4e3a 0",
                       "1048576", "120 \u79d2", "150 \u79d2", "9 KiB/s", "1%", "maxRetries=5"):
            self.assertIn(marker, text)

    def test_p52_partial_is_not_complete_or_release(self):
        text = self.read("docs/ota-prompts/prompt-P5-2-acceptance.md")
        for marker in ("03/05/07/15/16/17", "P5-1 \u4e3b\u8def\u5f84\u4f9d\u8d56\u4ecd\u4fdd\u7559", "\u4e0d\u5220\u884c\u3001\u4e0d\u7b97 PASS",
                       "\u5b8c\u6574\u5fc5\u9009\u77e9\u9635", "\u9636\u6bb5\u6027\u8bc1\u636e\u4e0d\u662f\u6574\u5361\u5b8c\u6210", "\u751f\u4ea7\u664b\u5347"):
            self.assertIn(marker, text)

    def test_p53_is_draft_only_until_final_results(self):
        text = self.read("docs/ota-prompts/prompt-P5-3-acceptance.md")
        for marker in ("\u5148\u51c6\u5907\u6587\u6863\u8349\u7a3f", "\u65ad\u7535\u4e49\u52a1\u81ea\u52a8\u8f6c v2", "\u505c\u6b62\u6700\u7ec8\u6536\u53e3"):
            self.assertIn(marker, text)

    def test_release_gate_remains_closed_until_full_p5(self):
        text = self.read("docs/ota-cross-system-contracts.md")
        self.assertIn("reviewer \u660e\u786e\u6279\u51c6\u4e14 P5 \u9a8c\u6536\u901a\u8fc7\u540e", text)
        self.assertIn("\u7269\u7406\u7f3a\u9879\u4ecd\u963b\u65ad\u6574\u5361\u3001P5 \u6574\u4f53\u4e0e\u751f\u4ea7\u664b\u5347", text)

    def test_group16_successor_keeps_twenty_fault_types(self):
        text = self.read('docs/ota-prompts/prompt-P1-6-acceptance.md')
        rows = re.findall(r'(?m)^\| (\d{2}) \| (AUTO|PHYSICAL) \|', text)
        self.assertEqual(len(rows), 20)
        self.assertEqual([row for row, kind in rows if kind == 'PHYSICAL'], ['03','05','07','15','16','17'])
        for marker in ('OTA-DEC-019', 'K+1', '16', 'ROLLBACK', 'P5 statistics remain intact'):
            self.assertIn(marker, text)

    def test_group16_decision_reaches_forward_contracts(self):
        for path in ('PLAN-OTA.md', 'docs/ota-binary-contracts.md', 'PLAN-OTA-EXEC.md'):
            self.assertIn('OTA-DEC-019', self.read(path))
        text = self.read('docs/ota-spec-decisions.md')
        self.assertIn('### \u8bb0\u5f55 19', text)
        self.assertIn('> \u5c31\u6309\u52a0\u901f\u7248\u7684\u6765\uff0c\u539f\u6765P1\u7684\u90a3\u90e8\u5206\u5df2\u7ecf\u8fc7\u65f6\u4e86', text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
