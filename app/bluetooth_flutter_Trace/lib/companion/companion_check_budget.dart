import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';

/// Persistent allowance shared by automatic firmware-check triggers.
class CompanionCheckBudget {
  CompanionCheckBudget(this.preferences);
  final SharedPreferences preferences;
  static const key = 'companion_auto_check_budget_v1';
  static const spacing = Duration(hours: 1);

  ({String? reason, int nextAt, int count}) inspect(DateTime now) {
    final today = now.year * 10000 + now.month * 100 + now.day;
    final raw = preferences.getString(key);
    Map<String, dynamic> saved = {};
    if (raw != null) {
      try {
        saved = Map<String, dynamic>.from(jsonDecode(raw) as Map);
        if (saved['day'] is! int || saved['last'] is! int || saved['count'] is! int ||
            (saved['count'] as int) < 0 || (saved['count'] as int) > 3) {
          throw const FormatException();
        }
      } catch (_) {
        return (reason: 'quota_state_invalid', nextAt: 0, count: 3);
      }
    }
    final day = saved['day'] as int? ?? today;
    final last = saved['last'] as int? ?? 0;
    final count = today > day ? 0 : saved['count'] as int? ?? 0;
    final nextDay = DateTime(now.year, now.month, now.day + 1).millisecondsSinceEpoch;
    if (today < day || now.millisecondsSinceEpoch < last) {
      return (reason: 'clock_rollback', nextAt: last + spacing.inMilliseconds, count: count);
    }
    if (count >= 3) return (reason: 'daily_limit', nextAt: nextDay, count: count);
    if (last > 0 && now.millisecondsSinceEpoch - last < spacing.inMilliseconds) {
      return (reason: 'minimum_interval', nextAt: last + spacing.inMilliseconds, count: count);
    }
    return (reason: null, nextAt: now.millisecondsSinceEpoch, count: count);
  }

  Future<bool> reserve(DateTime now) async {
    final decision = inspect(now);
    if (decision.reason != null) return false;
    return preferences.setString(key, jsonEncode({
      'day': now.year * 10000 + now.month * 100 + now.day,
      'last': now.millisecondsSinceEpoch, 'count': decision.count + 1,
    }));
  }
}
