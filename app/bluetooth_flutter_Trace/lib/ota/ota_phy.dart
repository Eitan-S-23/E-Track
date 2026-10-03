import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';

typedef PhyMethodInvoker = Future<Object?> Function(
    String method, Map<String, Object?> arguments);

/// Actual Android readback, not the successful invocation of setPreferredPhy.
class OtaPhyObservation {
  OtaPhyObservation(Map<String, Object?> value)
      : fields = Map<String, Object?>.unmodifiable(value);

  final Map<String, Object?> fields;

  bool get permitsTransfer =>
      fields['status'] == 'observed' &&
      (fields['policy'] == 'observe' ||
          (fields['txPhy'] == 2 && fields['rxPhy'] == 2));
}

class OtaPhyClient {
  const OtaPhyClient({this.invoke, this.isAndroid});

  static const channel = MethodChannel('etrack/ota_phy');
  final PhyMethodInvoker? invoke;
  final bool? isAndroid;

  Future<OtaPhyObservation> observe({required String policy,
      required String remoteId, required String requestId}) async {
    if (!const {'observe', 'prefer2m'}.contains(policy)) {
      throw ArgumentError.value(policy, 'policy');
    }
    final address = remoteId.toUpperCase();
    final binding = <String, Object?>{
      'policy': policy, 'remoteId': address, 'requestId': requestId,
    };
    OtaPhyObservation failed(String reason) => OtaPhyObservation({
      ...binding, 'status': reason,
    });
    if (!(isAndroid ?? (!kIsWeb && defaultTargetPlatform == TargetPlatform.android))) {
      return failed('unsupported-platform');
    }
    try {
      final raw = await (invoke != null
          ? invoke!('p34ObservePhy', binding)
          : channel.invokeMethod<Object?>('p34ObservePhy', binding))
          .timeout(const Duration(seconds: 5));
      if (raw is! Map || raw['schema'] != 1 ||
          raw['remoteId'] != address || raw['requestId'] != requestId ||
          raw['policy'] != policy || raw['connectionGeneration'] is! int ||
          (raw['connectionGeneration'] as int) <= 0 ||
          raw['elapsedMicros'] is! int || (raw['elapsedMicros'] as int) < 0 ||
          !const {'observed', 'disconnected', 'timeout', 'read-failed',
            'update-failed', 'invalid-phy', 'native-call-failed'}.contains(raw['status'])) {
        return failed('invalid-native-result');
      }
      bool phy(Object? value) => value is int && value >= 1 && value <= 3;
      if (raw['status'] == 'observed' &&
          (!phy(raw['beforeTxPhy']) || !phy(raw['beforeRxPhy']) ||
           !phy(raw['txPhy']) || !phy(raw['rxPhy']) ||
           raw['beforeReadStatus'] != 0 ||
           (policy == 'prefer2m' && (raw['updateStatus'] != 0 ||
               raw['readStatus'] != 0 || !phy(raw['updateTxPhy']) ||
               !phy(raw['updateRxPhy']))))) {
        return failed('invalid-native-result');
      }
      if (raw.keys.any((key) => key is! String)) return failed('invalid-native-result');
      return OtaPhyObservation(Map<String, Object?>.from(raw));
    } on TimeoutException {
      return failed('channel-timeout');
    } on PlatformException catch (error) {
      return failed('platform-error:${error.code}');
    } on MissingPluginException {
      return failed('plugin-unavailable');
    }
  }
}
