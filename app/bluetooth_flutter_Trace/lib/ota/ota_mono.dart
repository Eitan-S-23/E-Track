import 'package:flutter/foundation.dart';

/// OTA 观测插桩专用单调时钟（P3-3 T1a 设备观测；dev 分支 + dev APK）。
///
/// 全进程唯一实例：所有 `OTA_MONO` 行都带 `monoUs`，判据只用**同类事件**的
/// `monoUs` 差值。`wallUs`（墙钟微秒）只用于与 logcat 行、操作时间线对齐，
/// **不参与任何判据**——它的起点与本时钟相同，但两者之差不是任何等待时长；
/// 传输内预算时钟在 transfer 入口才启动，与进程级起点不同，更不可相减。
final Stopwatch otaMono = Stopwatch()..start();

/// 输出一行 `OTA_MONO <event> monoUs=<n> wallUs=<n> [code=..] [durable=..]`。
///
/// 值在调用点构造，不受日志投递延迟影响；只读时钟、不改变任何控制流。
void otaMonoLog(String event, {String? code, int? durable}) {
  final line = StringBuffer('OTA_MONO $event')
    ..write(' monoUs=${otaMono.elapsedMicroseconds}')
    ..write(' wallUs=${DateTime.now().microsecondsSinceEpoch}');
  if (code != null) {
    line.write(' code=$code');
  }
  if (durable != null) {
    line.write(' durable=$durable');
  }
  debugPrint(line.toString());
}
