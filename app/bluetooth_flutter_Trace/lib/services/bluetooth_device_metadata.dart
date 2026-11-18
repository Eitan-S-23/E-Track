import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:get/get.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Display metadata for previously connected devices, never live link authority.
class BluetoothDeviceMetadata {
  BluetoothDeviceMetadata({Future<SharedPreferences> Function()? preferences})
      : _preferences = preferences ?? SharedPreferences.getInstance;

  static const storageKey = 'bluetooth_connected_device_names_v1';
  static const capacity = 64;
  final Future<SharedPreferences> Function() _preferences;
  final _names = <String, String>{}.obs;
  Future<void>? _restoration;
  Future<void> _writes = Future.value();
  bool _closed = false;

  static String keyOf(String address) => address.trim().toLowerCase();

  static String? usableName(String? value) {
    final name = value?.trim() ?? '';
    if (name.isEmpty || name.length > 248 ||
        name == '\u672a\u77e5\u8bbe\u5907' || name.toLowerCase() == 'unknown device') {
      return null;
    }
    return name;
  }

  String? nameOf(String address) => usableName(_names[keyOf(address)]);
  bool wasConnected(String address) => _names.containsKey(keyOf(address));

  Future<void> restore() => _restoration ??= _restore();

  Future<void> _restore() async {
    try {
      final prefs = await _preferences().timeout(const Duration(seconds: 2));
      final raw = prefs.getString(storageKey);
      final restored = <String, String>{};
      if (raw != null && raw.length <= 32768) {
        final decoded = jsonDecode(raw);
        if (decoded is Map<String, dynamic>) {
          for (final entry in decoded.entries) {
            final key = keyOf(entry.key);
            if (key.isNotEmpty && key.length <= 128 && entry.value is String) {
              restored[key] = usableName(entry.value as String) ?? '';
            }
          }
        }
      }
      if (_closed) return;
      // A live update wins a slow disk read; a nameless reconnect keeps the old name.
      for (final entry in _names.entries) {
        restored[entry.key] = usableName(entry.value) ?? restored[entry.key] ?? '';
      }
      _trim(restored);
      _names.assignAll(restored);
    } catch (_) {
      debugPrint('Bluetooth display metadata restore unavailable');
    }
  }

  void rememberConnection(String address, {String? name}) {
    if (_closed) return;
    final key = keyOf(address);
    if (key.isEmpty || key.length > 128) return;
    final value = usableName(name) ?? _names[key] ?? '';
    if (_names.containsKey(key) && _names[key] == value) return;
    final next = Map<String, String>.from(_names)..remove(key);
    next[key] = value;
    _trim(next);
    _names.assignAll(next);
    _writes = _writes.then((_) async {
      await restore();
      if (_closed) return;
      final prefs = await _preferences().timeout(const Duration(seconds: 2));
      if (_closed) return;
      final ok = await prefs.setString(storageKey, jsonEncode(_names.value))
          .timeout(const Duration(seconds: 2));
      if (!ok) throw StateError('Device metadata write rejected');
    }).catchError((Object _) {
      debugPrint('Bluetooth display metadata save unavailable');
    });
  }

  static void _trim(Map<String, String> names) {
    while (names.length > capacity) {
      names.remove(names.keys.first);
    }
  }

  Future<void> get settled async {
    await restore();
    await _writes;
  }

  void close() => _closed = true;
}
