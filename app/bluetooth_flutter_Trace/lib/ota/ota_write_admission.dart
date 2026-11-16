/// One chunk's synchronous gate at the final project-owned write boundary.
/// A successful [dispatch] must be followed by the platform call without awaiting.
class OtaWriteAdmission {
  OtaWriteAdmission(this._check);

  final void Function() _check;
  bool _dispatched = false;
  bool _rejected = false;
  bool _retired = false;

  bool get dispatched => _dispatched;
  bool get rejected => _rejected;

  void dispatch() {
    try {
      if (_retired || _dispatched) {
        throw StateError('OTA_WRITE_ADMISSION_RETIRED');
      }
      _check();
    } catch (_) {
      _rejected = !_dispatched;
      _retired = true;
      rethrow;
    }
    _dispatched = true;
  }

  /// A timed-out discovery must not dispatch after its writer has yielded.
  void retire() => _retired = true;
}
