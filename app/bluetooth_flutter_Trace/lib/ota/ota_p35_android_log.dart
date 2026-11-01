import 'dart:convert';
import 'dart:ffi';

import 'package:ffi/ffi.dart';

typedef AndroidLogWrite = int Function(
  int priority, Pointer<Utf8> tag, Pointer<Utf8> message);
typedef _NativeLogWrite = Int32 Function(
  Int32 priority, Pointer<Utf8> tag, Pointer<Utf8> message);

final AndroidLogWrite _androidWrite = DynamicLibrary.open('liblog.so')
    .lookupFunction<_NativeLogWrite, AndroidLogWrite>('__android_log_write');

/// Native acceptance is necessary, but the host still proves live delivery.
void emitP35AndroidLog(String line, {AndroidLogWrite? write}) {
  if (!line.startsWith('OTA_P35_STATE ') &&
      !line.startsWith('OTA_P35_CAPTURE ') &&
      !line.startsWith('OTA_P35_ERROR ')) {
    throw ArgumentError('Not a P35 record');
  }
  if (line.contains('\n') || line.contains('\r') || line.contains('\x00') ||
      utf8.encode(line).length > 3500) {
    throw ArgumentError('P35 log record exceeds native single-line bounds');
  }
  final nativeWrite = write ?? _androidWrite;
  final tag = 'ETrackP35'.toNativeUtf8();
  Pointer<Utf8>? message;
  try {
    message = line.toNativeUtf8();
    if (nativeWrite(4, tag, message) <= 0) {
      throw StateError('Android log writer rejected P35 record');
    }
  } finally {
    if (message != null) malloc.free(message);
    malloc.free(tag);
  }
}
