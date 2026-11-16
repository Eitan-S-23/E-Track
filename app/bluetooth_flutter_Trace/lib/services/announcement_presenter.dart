import 'dart:async';

import 'package:flutter/widgets.dart';

import '../pages/discover_tab_page.dart';
import 'announcement_service.dart';
import 'app_prompt_coordinator.dart';

/// Main-screen lifetime only; never polls or opens a window in a headless engine.
class AnnouncementPresenter {
  AnnouncementPresenter({required this.canPresent});

  final bool Function() canPresent;
  Timer? _timer;
  DateTime? _lastFetch;
  AppPrompt<void>? _prompt;
  bool _fetching = false;
  bool _disposed = false;

  void start() {
    _timer ??= Timer.periodic(const Duration(minutes: 5), (_) => unawaited(refresh()));
    unawaited(refresh());
  }

  Future<void> refresh() async {
    if (_disposed || _fetching || _prompt != null ||
        WidgetsBinding.instance.lifecycleState != AppLifecycleState.resumed) return;
    final now = DateTime.now();
    if (_lastFetch != null && now.difference(_lastFetch!) < const Duration(minutes: 1)) return;
    _lastFetch = now;
    _fetching = true;
    try {
      final items = await AnnouncementService.unseen(
          await AnnouncementService.fetchRemoteAnnouncements());
      if (_disposed || items.isEmpty) return;
      final prompt = createAnnouncementPrompt(
        announcements: items,
        automatic: true,
        ready: canPresent,
      );
      _prompt = prompt;
      unawaited(prompt.closed.whenComplete(() {
        if (identical(_prompt, prompt)) _prompt = null;
      }));
    } catch (_) {
      // A failed read is not a new announcement or an instruction to show fallback.
    } finally {
      _fetching = false;
    }
  }

  void dispose() {
    _disposed = true;
    _timer?.cancel();
    _prompt?.cancel();
  }
}
