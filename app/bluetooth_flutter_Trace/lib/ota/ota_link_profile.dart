/// Build intent only. Receiver capabilities and GATT properties remain decisive.
class OtaLinkProfile {
  const OtaLinkProfile._(this.name, this.pipeline, this.reuseGatt,
      this.preferWithoutResponse, this.windowSegments, this.batchFrames);

  static const baseline = OtaLinkProfile._('baseline', false, false, false, 4, 1);
  static const adaptiveCandidate = OtaLinkProfile._(
      'adaptive-v2-candidate', true, true, true, 24, 12);

  static OtaLinkProfile get build => parse(const String.fromEnvironment(
      'OTA_LINK_PROFILE', defaultValue: 'baseline'));

  static OtaLinkProfile parse(String name) => switch (name) {
    'baseline' => baseline,
    'adaptive-v2-candidate' => adaptiveCandidate,
    _ => throw ArgumentError.value(name, 'OTA_LINK_PROFILE', 'unknown profile'),
  };

  final String name;
  final bool pipeline, reuseGatt, preferWithoutResponse;
  final int windowSegments, batchFrames;

  Map<String, Object> get requested => {
    'profile': name, 'protocol': pipeline ? 2 : 1,
    'windowSegments': windowSegments, 'dataBatchFrames': batchFrames,
    'reuseGatt': reuseGatt, 'preferWithoutResponse': preferWithoutResponse,
  };
}

/// Published only after a valid BEGIN ACK, never inferred from build metadata.
class OtaTransportSelection {
  const OtaTransportSelection({required this.protocol,
    required this.windowSegments, required this.dataBatchFrames,
    this.fallbackReason});
  final int protocol, windowSegments, dataBatchFrames;
  final String? fallbackReason;

  Map<String, Object?> toJson() => {
    'protocol': protocol, 'windowSegments': windowSegments,
    'dataBatchFrames': dataBatchFrames, 'fallbackReason': fallbackReason,
  };

  String get summary => 'BLE v$protocol, window=$windowSegments, batch=$dataBatchFrames'
      '${fallbackReason == null ? '' : ' ($fallbackReason)'}';
}
