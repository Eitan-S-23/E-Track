import 'dart:convert';
import 'dart:ffi';

import 'package:ffi/ffi.dart';

typedef AndroidLogWrite = int Function(int tag, Pointer<Utf8> message);
typedef _NativeLogWrite = Int32 Function(Int32 tag, Pointer<Utf8> message);

const p35AndroidEventTag = 0x45545035;

class AndroidLogWriteFailure extends StateError {
  AndroidLogWriteFailure(this.result, this.expectedBytes)
      : super('Android log result=$result expected=$expectedBytes');

  final int result;
  final int expectedBytes;
}

final AndroidLogWrite _androidWrite = DynamicLibrary.open('liblog.so')
    .lookupFunction<_NativeLogWrite, AndroidLogWrite>('__android_log_bswrite');

/// Structured events avoid the process text-logger callback. The host still
/// proves timely delivery and exact equality with the persisted capture.
void emitP35AndroidLog(String line, {AndroidLogWrite? write}) {
  if (!line.startsWith('OTA_P35_STATE ') &&
      !line.startsWith('OTA_P35_CAPTURE ') &&
      !line.startsWith('OTA_P35_ERROR ')) {
    throw ArgumentError('Not a P35 record');
  }
  final byteLength = utf8.encode(line).length;
  if (line.contains('\n') || line.contains('\r') || line.contains('\x00') ||
      byteLength > 3500) {
    throw ArgumentError('P35 log record exceeds native single-line bounds');
  }
  final nativeWrite = write ?? _androidWrite;
  Pointer<Utf8>? message;
  try {
    message = line.toNativeUtf8();
    // Binary event framing is tag(4), string type(1), length(4), then UTF-8.
    final result = nativeWrite(p35AndroidEventTag, message);
    if (result != byteLength + 9) {
      throw AndroidLogWriteFailure(result, byteLength + 9);
    }
  } finally {
    if (message != null) malloc.free(message);
  }
}
