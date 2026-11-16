import 'dart:async';

import 'package:flutter/material.dart';
import 'package:get/get.dart';

/// A ticket owns one route. Cancelling it never pops somebody else's dialog.
class AppPrompt<T> {
  AppPrompt._(this._owner, this.builder, this.priority, this.requireHome,
      this.ready, this.relevant, this.barrierDismissible);

  final AppPromptCoordinator _owner;
  final WidgetBuilder builder;
  final int priority;
  final bool requireHome;
  final bool Function()? ready;
  final bool Function()? relevant;
  final bool barrierDismissible;
  final _result = Completer<T?>();
  DialogRoute<T>? _route;
  bool _cancelled = false;

  Future<T?> get closed => _result.future;

  void cancel() {
    _cancelled = true;
    final route = _route;
    if (route != null && route.isActive) {
      route.navigator?.removeRoute(route);
    }
    _owner.notify();
  }

  Future<void> _present(NavigatorState navigator) async {
    final route = DialogRoute<T>(
      context: navigator.context,
      builder: builder,
      barrierDismissible: barrierDismissible,
      barrierColor: Colors.black.withValues(alpha: 0.62),
    );
    _route = route;
    try {
      final value = await navigator.push<T>(route);
      // push() completes when popping starts, not when its animation is gone.
      await route.completed;
      if (!_result.isCompleted) _result.complete(value);
    } catch (error, stack) {
      if (!_result.isCompleted) _result.completeError(error, stack);
    }
  }

  void _skip() {
    if (!_result.isCompleted) _result.complete();
  }
}

/// Serializes App update and announcement prompts without changing their UI.
class AppPromptCoordinator extends NavigatorObserver
    with WidgetsBindingObserver {
  static final instance = AppPromptCoordinator();
  static const updatePriority = 100;
  static const announcementPriority = 0;

  final _pending = <AppPrompt<dynamic>>[];
  final _routes = <Route<dynamic>>[];
  bool _observing = false;
  bool _scheduled = false;
  bool _active = false;
  int _retiring = 0;
  Timer? _retry;

  AppPrompt<T> enqueue<T>({
    required WidgetBuilder builder,
    int priority = announcementPriority,
    bool requireHome = false,
    bool Function()? ready,
    bool Function()? relevant,
    bool barrierDismissible = true,
  }) {
    if (!_observing) {
      WidgetsBinding.instance.addObserver(this);
      _observing = true;
    }
    final prompt = AppPrompt<T>._(this, builder, priority, requireHome, ready,
        relevant, barrierDismissible);
    _pending.add(prompt);
    notify();
    return prompt;
  }

  void notify() {
    if (_scheduled) return;
    _scheduled = true;
    scheduleMicrotask(() {
      _scheduled = false;
      unawaited(_drain());
    });
  }

  bool get _foreground {
    final state = WidgetsBinding.instance.lifecycleState;
    return state == null || state == AppLifecycleState.resumed;
  }

  Future<void> _drain() async {
    _retry?.cancel();
    _retry = null;
    _pending.removeWhere((prompt) {
      if (!prompt._cancelled && (prompt.relevant?.call() ?? true)) return false;
      prompt._skip();
      return true;
    });
    if (_active || _pending.isEmpty || !_foreground) return;
    final nav = navigator ?? Get.key.currentState;
    final top = _routes.isEmpty ? null : _routes.last;
    if (nav == null || _retiring != 0 || top is PopupRoute ||
        Get.isDialogOpen == true || Get.isBottomSheetOpen == true ||
        Get.currentRoute == '/companion-setup') {
      _retry = Timer(const Duration(milliseconds: 300), notify);
      return;
    }
    _pending.sort((a, b) => b.priority.compareTo(a.priority));
    final home = top == null ? Get.currentRoute == '/' : top.isFirst;
    final index = _pending.indexWhere((prompt) =>
        (!prompt.requireHome || home) && (prompt.ready?.call() ?? true));
    if (index < 0) {
      _retry = Timer(const Duration(milliseconds: 300), notify);
      return;
    }
    final prompt = _pending.removeAt(index);
    _active = true;
    try {
      await prompt._present(nav);
    } finally {
      _active = false;
      notify();
    }
  }

  @override
  void didPush(Route<dynamic> route, Route<dynamic>? previousRoute) {
    _routes.add(route);
    notify();
  }

  @override
  void didPop(Route<dynamic> route, Route<dynamic>? previousRoute) {
    _routes.remove(route);
    if (route is TransitionRoute<dynamic>) {
      _retiring++;
      unawaited(route.completed.whenComplete(() { _retiring--; notify(); }));
    }
    notify();
  }

  @override
  void didRemove(Route<dynamic> route, Route<dynamic>? previousRoute) {
    _routes.remove(route);
    notify();
  }

  @override
  void didReplace({Route<dynamic>? newRoute, Route<dynamic>? oldRoute}) {
    final index = oldRoute == null ? -1 : _routes.indexOf(oldRoute);
    if (index >= 0) {
      if (newRoute == null) { _routes.removeAt(index); }
      else { _routes[index] = newRoute; }
    }
    notify();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) { notify(); }
    else { _retry?.cancel(); _retry = null; }
  }

  void dispose() {
    for (final prompt in _pending) { prompt._skip(); }
    _pending.clear();
    _retry?.cancel();
    if (_observing) WidgetsBinding.instance.removeObserver(this);
    _observing = false;
  }
}
