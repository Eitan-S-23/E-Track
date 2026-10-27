import 'package:flutter/material.dart';
import 'package:get/get.dart';

/// Startup services can report an error before a Navigator/Overlay exists.
void safeSnackbar(String title, String message,
    {BuildContext? context,
    SnackPosition snackPosition = SnackPosition.BOTTOM,
    Color? backgroundColor, Color? colorText}) {
  WidgetsBinding.instance.addPostFrameCallback((_) {
    final target = context ?? Get.key.currentContext;
    if (target == null || !target.mounted) return;
    if (context != null) {
      // Page feedback must not leak onto a replacement/covered route or queue
      // across a navigation animation. Service notifications keep their root scope.
      final route = ModalRoute.of(target);
      final animation = route?.animation?.status;
      final lifecycle = WidgetsBinding.instance.lifecycleState;
      if (route?.isCurrent == false || animation == AnimationStatus.forward ||
          animation == AnimationStatus.reverse ||
          (lifecycle != null && lifecycle != AppLifecycleState.resumed)) return;
    }
    final messenger = ScaffoldMessenger.maybeOf(target);
    if (messenger == null) return;
    try {
      messenger.showSnackBar(SnackBar(backgroundColor: backgroundColor,
          content: Text('$title: $message', style: TextStyle(color: colorText))));
    } on FlutterError catch (error) {
      if (!error.message.contains('there are currently no descendant Scaffolds')) {
        rethrow;
      }
      // This specific dependency can be absent during service startup/teardown.
      debugPrint('UI notification unavailable: $title');
    }
  });
  WidgetsBinding.instance.ensureVisualUpdate();
}
