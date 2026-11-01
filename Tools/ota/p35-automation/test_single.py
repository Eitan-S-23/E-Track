"""Development single-upgrade profile; no physical observations in these tests."""
import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runner as r
import pipeline as p
import test_runner as unit
import test_campaign as integration
import test_pipeline as pipeline_fixture


def single_plan():
    plan = unit.plan()
    plan.update(test_profile='single-upgrade', cases=[], allow_bluetooth_toggle=False)
    return plan


class SingleTests(unittest.TestCase):
    def test_explicit_profile_cannot_enter_ten_case_validator(self):
        plan = single_plan()
        self.assertEqual(r.validate_plan(plan, single=True), plan)
        with self.assertRaises(r.Stop):
            r.validate_plan(plan)
        with self.assertRaises(r.Stop):
            r.validate_plan(unit.plan(), single=True)
        for change in ({'cases': unit.plan()['cases']}, {'allow_bluetooth_toggle': True},
                       {'test_profile': 'typo'}):
            with self.subTest(change=change), self.assertRaises(r.Stop):
                r.validate_plan(dict(plan, **change), single=True)

    def test_complete_single_has_no_radio_calls_and_requires_full_identity(self):
        plan = single_plan()
        for fault in (None, 'hash', 'version', 'fresh', 'durable', 'terminal'):
            rows = unit.trace(plan)
            if fault == 'hash': rows[-1]['currentImageSha256'] = 'f' * 64
            if fault == 'version': rows[-1]['currentVersionCode'] = 30293
            if fault == 'fresh': rows[-1]['freshConnection'] = False
            if fault == 'durable': rows[-1]['durable'] = 0
            if fault == 'terminal': rows[-1]['phase'] = 'waitingReboot'
            driver = unit.Fake(rows)
            campaign = r.Campaign(plan, driver, driver.clock, single=True)
            if fault is None:
                result = campaign.run()
                self.assertEqual(result['outcome'], 'AUTOMATION_COMPLETED')
                self.assertEqual(result['recovered'], 0)
            else:
                with self.subTest(fault=fault), self.assertRaises(r.Stop):
                    campaign.run()
            self.assertFalse(any(action[0] == 'radio' for action in driver.actions))

    def test_pipeline_profile_does_not_generate_or_accept_ten_windows(self):
        config, template, target, _ = pipeline_fixture.fixture()
        config['test_profile'] = 'single-upgrade'
        template.update(test_profile='single-upgrade', cases=[], allow_bluetooth_toggle=False)
        before = copy.deepcopy(template)
        self.assertEqual(p.validate(config), 30295)
        actual = p.make_plan(template, config, target)
        self.assertEqual(actual['cases'], [])
        self.assertEqual(template, before)
        self.assertFalse(actual['allow_bluetooth_toggle'])
        with self.assertRaises(r.Stop):
            p.make_plan(template, pipeline_fixture.fixture()[0], target)
        config['test_profile'] = 'ten-ish'
        with self.assertRaises(r.Stop):
            p.validate(config)


class SingleDevice(integration.Device):
    def command(self, args):
        before = self.upgrade_starts
        result = super().command(args)
        if not before and self.upgrade_starts:
            self.completed = True
            self.push(self.transfer(event='data', sendOffset=0))
            self.push(self.transfer(durable=4096))
            self.push(unit.state(protocol=2, bitmap=None, phase='completed', event='identity',
                currentVersionCode=30294, currentImageSha256='d' * 64, durable=1048576))
        return result


class SingleIntegrationTests(unittest.TestCase):
    def test_real_entry_single_capture_no_update_archive_and_cleanup(self):
        integration.IntegrationTests.setUpClass()
        case = integration.IntegrationTests()
        with patch.object(integration, 'Device', SingleDevice):
            code, result, device, out, lock = case.run_case(single=True)
        self.assertEqual(code, 0)
        self.assertEqual(result['semantics'], 'single-upgrade-no-injection')
        self.assertEqual(result['planned'], 0)
        self.assertEqual(result['caseResults'], [])
        self.assertEqual(result['recovered'], 0)
        self.assertEqual(result['noUpdate']['outcome'], 'NO_UPDATE')
        self.assertEqual((device.arms, device.stops, device.upgrade_starts), (1, 1, 1))
        self.assertFalse(any(c[:3] == ['shell', 'cmd', 'bluetooth_manager'] for c in device.calls))
        self.assertTrue(result['cleanup']['complete'])
        self.assertFalse(lock.exists())
        self.assertEqual((out / 'app-capture.jsonl').read_bytes(), device.raw)


if __name__ == '__main__':
    unittest.main()
