import 'package:flutter/material.dart';
import 'package:get/get.dart';

/// Startup services can report an error before a Navigator/Overlay exists.
void safeSnackbar(String title, String message,
    {SnackPosition snackPosition = SnackPosition.BOTTOM}) {
  WidgetsBinding.instance.addPostFrameCallback((_) {
    final context = Get.key.currentContext;
    if (context == null || !context.mounted) return;
    final messenger = ScaffoldMessenger.maybeOf(context);
    try {
      messenger?.showSnackBar(SnackBar(content: Text('$title: $message')));
    } on FlutterError {
      // A route transition can temporarily leave the messenger without a Scaffold.
      debugPrint('UI notification unavailable: $title');
    }
  });
  WidgetsBinding.instance.ensureVisualUpdate();
}
