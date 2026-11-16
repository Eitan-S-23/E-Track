import 'dart:io';
import 'package:flutter/services.dart';

class CompanionPlatform {
  CompanionPlatform({MethodChannel? channel, bool? supported})
      : channel = channel ?? const MethodChannel('trace/companion'),
        supported = supported ?? Platform.isAndroid;

  final MethodChannel channel;
  final bool supported;

  Future<Map<String, dynamic>> snapshot() async {
    if (!supported) return {'enabled': false, 'problem': 'ANDROID_ONLY'};
    return await channel.invokeMapMethod<String, dynamic>('snapshot') ??
        {'enabled': false, 'problem': 'PLATFORM_UNAVAILABLE'};
  }

  Future<Map<String, dynamic>> configure({required bool enabled,
      required int intervalHours, required bool wifiOnly}) async {
    if (!supported) throw UnsupportedError('ANDROID_ONLY');
    return await channel.invokeMapMethod<String, dynamic>('configure', {
      'enabled': enabled, 'intervalHours': intervalHours, 'wifiOnly': wifiOnly,
    }) ?? (throw StateError('CONFIGURATION_UNCONFIRMED'));
  }

  Future<Map<String, dynamic>> associate(String address) async =>
      await channel.invokeMapMethod<String, dynamic>('associate', {'address': address}) ??
      (throw StateError('ASSOCIATION_UNCONFIRMED'));

  Future<bool> openSettings(String kind) async =>
      await channel.invokeMethod<bool>('settings', {'kind': kind}) == true;

  Future<void> check() async { await channel.invokeMethod<Object?>('check'); }
}
