import 'dart:convert';
import 'package:ble_monitor/companion/companion_check_budget.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late SharedPreferences prefs;
  late CompanionCheckBudget budget;
  final start = DateTime(2026, 11, 22, 8);
  setUp(() async {
    SharedPreferences.setMockInitialValues({});
    prefs = await SharedPreferences.getInstance();
    budget = CompanionCheckBudget(prefs);
  });
  test('three attempts, spacing, persisted restart and next local day', () async {
    expect(await budget.reserve(start), isTrue);
    expect(budget.inspect(start.add(const Duration(minutes: 59))).reason, 'minimum_interval');
    expect(await budget.reserve(start.add(const Duration(hours: 1))), isTrue);
    budget = CompanionCheckBudget(await SharedPreferences.getInstance());
    expect(await budget.reserve(start.add(const Duration(hours: 2))), isTrue);
    expect(await budget.reserve(start.add(const Duration(hours: 3))), isFalse);
    expect(budget.inspect(start.add(const Duration(hours: 3))).reason, 'daily_limit');
    expect(await budget.reserve(start.add(const Duration(days: 1))), isTrue);
  });
  test('rollback cannot reset the day or bypass spacing', () async {
    expect(await budget.reserve(start), isTrue);
    expect(budget.inspect(start.subtract(const Duration(days: 1))).reason, 'clock_rollback');
    expect(budget.inspect(start.subtract(const Duration(minutes: 1))).reason, 'clock_rollback');
  });
  test('midnight keeps minimum spacing', () async {
    await budget.reserve(DateTime(2026, 11, 22, 23, 50));
    expect(budget.inspect(DateTime(2026, 11, 23, 0, 5)).reason, 'minimum_interval');
    expect(await budget.reserve(DateTime(2026, 11, 23, 0, 50)), isTrue);
  });
  test('skipped inspection does not spend quota, malformed state fails closed', () async {
    budget.inspect(start);
    expect(prefs.containsKey(CompanionCheckBudget.key), isFalse);
    await prefs.setString(CompanionCheckBudget.key, jsonEncode({'count': -1}));
    expect(budget.inspect(start).reason, 'quota_state_invalid');
    expect(await budget.reserve(start), isFalse);
  });
}
