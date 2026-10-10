import 'ota_ble_transport.dart';

const defaultRebootInfoAttempts = 3;
const maxRebootInfoAttempts = 12;

/// Reuse only a still-owned probe binding after a completed INFO timeout.
/// The caller retains its outer attempt deadline and identity checks.
Future<T?> retryInfoOnCurrentLink<T>({
  required Future<T> Function() query,
  required bool Function() isCurrent,
  required Duration interval,
  int maxAttempts = defaultRebootInfoAttempts,
}) async {
  RangeError.checkValueInInterval(maxAttempts, 1, maxRebootInfoAttempts, 'maxAttempts');
  if (interval < Duration.zero) throw ArgumentError.value(interval, 'interval');
  for (var attempt = 0; attempt < maxAttempts; attempt++) {
    if (!isCurrent()) return null;
    try {
      final value = await query();
      return isCurrent() ? value : null;
    } on OtaTransportException catch (error) {
      if (!isCurrent()) return null;
      if (error.code != 'TIMEOUT' || attempt + 1 == maxAttempts) rethrow;
    }
    await Future<void>.delayed(interval);
  }
  return null;
}
