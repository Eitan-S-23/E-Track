import 'package:ble_monitor/companion/companion_scan_policy.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('only the live owner can obtain a bounded background scan window', () {
    var now = 0;
    final policy = CompanionScanPolicy(nowMs: () => now);
    expect(policy.open('old'), isFalse);
    policy.ownerChanged('a');
    expect(policy.open('old'), isFalse);
    expect(policy.open('a'), isTrue);
    now = 7999; expect(policy.allowed, isTrue);
    now = 8000; expect(policy.allowed, isFalse);
    expect(policy.open('a'), isFalse);
    now = 60000; expect(policy.open('a'), isTrue);
    policy.close(); expect(policy.allowed, isFalse);
    expect(policy.open('a'), isFalse);
  });
  test('revocation and replacement invalidate late scans immediately', () {
    final policy = CompanionScanPolicy(nowMs: () => 100);
    policy.ownerChanged('a'); policy.open('a');
    policy.ownerChanged(null); expect(policy.allowed, isFalse);
    expect(policy.open('a'), isFalse);
    policy.ownerChanged('b'); expect(policy.open('a'), isFalse);
    expect(policy.open('b'), isTrue);
    policy.ownerChanged('b'); expect(policy.allowed, isTrue);
  });
}
