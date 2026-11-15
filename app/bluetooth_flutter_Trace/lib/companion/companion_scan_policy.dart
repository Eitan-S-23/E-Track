/// A short scan lease is not a general background execution permission.
class CompanionScanPolicy {
  CompanionScanPolicy({required this.nowMs});
  final int Function() nowMs;
  String? _owner;
  int _until = 0;
  int _next = 0;
  static const window = Duration(seconds: 8);
  static const interval = Duration(minutes: 1);

  void ownerChanged(String? owner) {
    if (_owner == owner) return;
    _owner = owner;
    _until = 0;
    _next = 0;
  }

  bool open(String owner) {
    final now = nowMs();
    if (_owner == null || owner != _owner || now < _next) return false;
    _until = now + window.inMilliseconds;
    _next = now + interval.inMilliseconds;
    return true;
  }

  bool get allowed => _owner != null && nowMs() < _until;
  void close() { _until = 0; }
}
