import 'package:flutter/services.dart';
import 'package:flutter/widgets.dart';
import 'package:get/get.dart';

class DeepLinkService extends GetxService {
  static const MethodChannel _channel = MethodChannel('trace/deep_link');

  String? _lastHandledLink;
  DateTime? _lastHandledAt;

  @override
  void onInit() {
    super.onInit();
    _channel.setMethodCallHandler(_handleMethodCall);
    _readInitialLink();
  }

  Future<void> _readInitialLink() async {
    try {
      final link = await _channel.invokeMethod<String>('getInitialLink');
      _handleLink(link);
    } on MissingPluginException {
      // Desktop builds do not expose the mobile deep-link channel.
    } catch (error) {
      debugPrint('Deep link initialization error: $error');
    }
  }

  Future<dynamic> _handleMethodCall(MethodCall call) async {
    if (call.method == 'onDeepLink') {
      _handleLink(call.arguments as String?);
      return null;
    }
    throw MissingPluginException('Unknown deep link method: ${call.method}');
  }

  void _handleLink(String? link) {
    if (link == null || link.isEmpty) return;

    final now = DateTime.now();
    if (_lastHandledLink == link &&
        _lastHandledAt != null &&
        now.difference(_lastHandledAt!).inMilliseconds < 1200) {
      return;
    }

    _lastHandledLink = link;
    _lastHandledAt = now;

    final uri = Uri.tryParse(link);
    if (uri == null || uri.scheme != 'trace') return;

    final pathTarget =
        uri.pathSegments.isNotEmpty ? uri.pathSegments.first : null;
    final target = uri.host.isNotEmpty ? uri.host : pathTarget;
    final queryTarget =
        uri.queryParameters['target'] ?? uri.queryParameters['screen'];

    if (target == 'speedometer' ||
        target == 'ride' ||
        queryTarget == 'speedometer' ||
        queryTarget == 'ride') {
      _openSpeedometer();
    }
  }

  void _openSpeedometer() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (Get.currentRoute == '/speedometer') return;
      if (Get.currentRoute != '/main') {
        Get.offAllNamed('/main');
      }

      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (Get.currentRoute == '/speedometer') return;
        Get.toNamed('/speedometer');
      });
    });
  }
}
