import 'dart:async';

import 'package:flutter/material.dart';
import 'package:get/get.dart';

import '../services/feedback_service.dart';
import 'trace_ui.dart';

class FeedbackPage extends StatefulWidget {
  const FeedbackPage({super.key, this.service});
  final FeedbackService? service;
  @override
  State<FeedbackPage> createState() => _FeedbackPageState();
}

class _FeedbackPageState extends State<FeedbackPage> {
  late final FeedbackService _service;
  final _text = TextEditingController();
  bool _saving = false, _leaving = false;
  String? _notice;

  @override
  void initState() {
    super.initState();
    _service = widget.service ?? Get.find<FeedbackService>();
    _text.addListener(_changed);
    unawaited(_service.poll());
  }

  void _changed() { if (mounted) setState(() {}); }
  @override
  void dispose() { _text.dispose(); super.dispose(); }

  Future<bool> _confirm(String message) async => await showDialog<bool>(
    context: context,
    builder: (_) => TraceDialog(title: '\u786e\u8ba4', message: message, color: TraceColors.amber,
      actions: [
        TraceDialogAction(label: '\u53d6\u6d88', onPressed: (context) => Navigator.of(context).pop(false)),
        TraceDialogAction(label: '\u786e\u5b9a', isPrimary: true, onPressed: (context) => Navigator.of(context).pop(true)),
      ]),
  ) == true;

  Future<void> _leave() async {
    if (_leaving || _saving) return;
    _leaving = true;
    try {
      if (await _confirm('\u653e\u5f03\u5c1a\u672a\u63d0\u4ea4\u7684\u6587\u5b57\u5e76\u8fd4\u56de\uff1f\u5df2\u4fdd\u5b58\u7684\u5f85\u53d1\u9001\u53cd\u9988\u4e0d\u4f1a\u4e22\u5931\u3002') && mounted) {
        Navigator.of(context).pop();
      }
    } finally { _leaving = false; }
  }

  Future<void> _save() async {
    if (_saving) return;
    setState(() { _saving = true; _notice = null; });
    try {
      await _service.add(_text.text);
      if (!mounted) return;
      _text.clear();
      setState(() { _notice = '\u5df2\u4fdd\u5b58\u3002\u53d1\u9001\u6210\u529f\u540e\u4f1a\u79fb\u5165\u201c\u5df2\u63d0\u4ea4\u201d\u3002'; });
    } catch (error) {
      if (mounted) {
        setState(() { _notice = error.toString().contains('FEEDBACK_OUTBOX_FULL')
        ? '\u5f85\u53d1\u9001\u5217\u8868\u5df2\u6ee1\uff0850 \u6761\uff09\u3002\u8bf7\u7b49\u5f85\u53d1\u9001\u6216\u5220\u9664\u4e0d\u518d\u9700\u8981\u7684\u53cd\u9988\uff0c\u5f53\u524d\u6587\u5b57\u5df2\u4fdd\u7559\u3002'
        : '\u672a\u80fd\u4fdd\u5b58\uff0c\u8bf7\u68c0\u67e5\u5b57\u6570\u6216\u7a0d\u540e\u91cd\u8bd5\uff0c\u5f53\u524d\u6587\u5b57\u5df2\u4fdd\u7559\u3002'; });
      }
    } finally { if (mounted) setState(() { _saving = false; }); }
  }

  String _time(dynamic seconds) => seconds is int
      ? DateTime.fromMillisecondsSinceEpoch(seconds * 1000, isUtc: true).toLocal().toString().split('.').first : '';

  Widget _entry(Map<String, dynamic> item, {required bool sent}) => Container(
    margin: const EdgeInsets.only(top: 10), padding: const EdgeInsets.all(14),
    decoration: BoxDecoration(color: TraceColors.deep, borderRadius: BorderRadius.circular(16),
      border: Border.all(color: TraceColors.ocean)),
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [
        Expanded(child: Text(_time(sent ? item['submittedAt'] : item['createdAt']),
          style: const TextStyle(color: TraceColors.muted, fontSize: 12))),
        if (!sent && !_service.isSealed(item['id'] as String)) IconButton(
          tooltip: '\u5220\u9664\u5f85\u53d1\u9001\u53cd\u9988', icon: const Icon(Icons.delete_outline, color: TraceColors.muted),
          onPressed: _service.sending.value ? null : () async {
            if (!await _confirm('\u5220\u9664\u8fd9\u6761\u5c1a\u672a\u53d1\u9001\u7684\u53cd\u9988\uff1f')) return;
            try { await _service.remove(item['id'] as String); }
            catch (_) { if (mounted) setState(() { _notice = '\u6682\u65f6\u65e0\u6cd5\u5220\u9664\uff0c\u53cd\u9988\u4ecd\u88ab\u4fdd\u7559\u3002'; }); }
          },
        ),
      ]),
      SelectableText(item['body'] as String, style: const TextStyle(color: TraceColors.text, height: 1.5)),
      if (!sent && _service.isSealed(item['id'] as String))
        const Text('\u7b49\u5f85\u786e\u8ba4\u53d1\u9001\u7ed3\u679c\uff0c\u91cd\u8bd5\u4e0d\u4f1a\u91cd\u590d\u5165\u5e93\u3002', style: TextStyle(color: TraceColors.muted, fontSize: 12)),
    ]),
  );

  @override
  Widget build(BuildContext context) => PopScope<void>(
    canPop: _text.text.trim().isEmpty && !_saving,
    onPopInvokedWithResult: (didPop, _) { if (!didPop) unawaited(_leave()); },
    child: TraceBackGesture(child: Scaffold(
      backgroundColor: TraceColors.ink,
      appBar: AppBar(backgroundColor: TraceColors.ink, foregroundColor: TraceColors.text,
        title: const Text('\u63d0\u4ea4\u53cd\u9988'),
        leading: IconButton(key: const ValueKey('detail-back'), tooltip: '\u8fd4\u56de',
          onPressed: () => TraceBackGesture.back(context), icon: const Icon(Icons.arrow_back))),
      body: TracePageScaffold(child: SafeArea(child: SingleChildScrollView(
        padding: const EdgeInsets.all(24), child: Obx(() {
          final pending = _service.pending, sent = _service.sent;
          final waiting = _service.nextAttemptAt;
          return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            const Text('\u63cf\u8ff0\u9047\u5230\u7684\u95ee\u9898\u6216\u4f60\u7684\u5efa\u8bae', style: TextStyle(color: TraceColors.text, fontSize: 20)),
            const SizedBox(height: 12),
            TextField(key: const ValueKey('feedback-text'), controller: _text,
              maxLength: 2000, minLines: 5, maxLines: 10, enabled: !_saving,
              style: const TextStyle(color: TraceColors.text),
              decoration: const InputDecoration(hintText: '\u53ef\u4ee5\u8bf4\u660e\u64cd\u4f5c\u6b65\u9aa4\u3001\u9884\u671f\u7ed3\u679c\u548c\u5b9e\u9645\u8868\u73b0\u3002\u8bf7\u52ff\u586b\u5199\u5bc6\u7801\u7b49\u654f\u611f\u4fe1\u606f\u3002',
                hintStyle: TextStyle(color: TraceColors.muted), counterStyle: TextStyle(color: TraceColors.muted),
                border: OutlineInputBorder())),
            const SizedBox(height: 8),
            const Text('\u4ec5\u63d0\u4ea4\u4f60\u586b\u5199\u7684\u6587\u5b57\u548c App \u7248\u672c\u3001\u5e73\u53f0\u4fe1\u606f\uff0c\u4e0d\u81ea\u52a8\u9644\u5e26\u65e5\u5fd7\u6216\u6587\u4ef6\u3002\u670d\u52a1\u5668\u4fdd\u7559\u53cd\u9988\u6b63\u6587 90 \u5929\u3002',
              style: TextStyle(color: TraceColors.muted, height: 1.5)),
            const SizedBox(height: 12),
            FilledButton.icon(key: const ValueKey('feedback-submit'),
              onPressed: !_service.available || !_service.ready.value || _saving || _text.text.trim().isEmpty ? null : _save,
              icon: const Icon(Icons.send_outlined), label: Text(_saving ? '\u6b63\u5728\u4fdd\u5b58' : '\u63d0\u4ea4\u53cd\u9988')),
            const Text('\u6bcf\u5929\u6700\u591a\u63d0\u4ea4\u4e00\u6279\uff0810 \u6761\uff09\uff0c\u540c\u4e00\u51fa\u53e3 IP \u6bcf\u5929\u5171\u4eab 50 \u6279\u989d\u5ea6\u3002\u8d85\u989d\u6216\u79bb\u7ebf\u65f6\u5148\u4fdd\u5b58\u5728\u672c\u673a\uff0c\u4e0b\u6b21\u524d\u53f0\u8054\u7f51\u540e\u518d\u53d1\u9001\u3002',
              style: TextStyle(color: TraceColors.muted, fontSize: 12, height: 1.5)),
            if (_notice != null) Padding(padding: const EdgeInsets.only(top: 12),
              child: Text(_notice!, key: const ValueKey('feedback-notice'), style: const TextStyle(color: TraceColors.amber))),
            if (_service.sending.value) const LinearProgressIndicator(),
            if (_service.failure.value != null) Padding(padding: const EdgeInsets.only(top: 12), child: Text(
              switch (_service.failure.value) {
                'LOCAL_STORAGE_UNAVAILABLE' => '\u672c\u5730\u53cd\u9988\u6682\u4e0d\u53ef\u7528\uff0c\u539f\u6709\u6570\u636e\u672a\u88ab\u8986\u76d6\u3002',
                'IP_DAILY_LIMIT' => '\u5f53\u524d\u7f51\u7edc\u4eca\u65e5\u989d\u5ea6\u5df2\u7528\u5b8c\uff0c\u53cd\u9988\u5df2\u4fdd\u7559\u3002',
                'RATE_LIMITED' => '\u5df2\u8fbe\u5230\u63d0\u4ea4\u9891\u7387\u9650\u5236\uff0c\u53cd\u9988\u5df2\u4fdd\u7559\u3002',
                'SUBMISSION_REJECTED' => '\u670d\u52a1\u7aef\u672a\u63a5\u6536\uff0c\u53cd\u9988\u5df2\u4fdd\u7559\uff0c\u53ef\u7a0d\u540e\u91cd\u8bd5\u3002',
                _ => '\u6682\u672a\u6536\u5230\u53d1\u9001\u786e\u8ba4\uff0c\u5c06\u81ea\u52a8\u91cd\u8bd5\uff0c\u53cd\u9988\u4e0d\u4f1a\u88ab\u4e22\u5f03\u3002',
              }, style: const TextStyle(color: TraceColors.amber))),
            if (pending.isNotEmpty && waiting != null) Text('\u4e0b\u6b21\u53ef\u5c1d\u8bd5\uff1a${waiting.toString().split('.').first}\uff08\u9700 App \u524d\u53f0\u8054\u7f51\uff09',
              style: const TextStyle(color: TraceColors.muted)),
            if (pending.isNotEmpty) TextButton.icon(onPressed: _service.sending.value ? null : () async {
              try { await _service.retry(); } catch (_) { /* The original queue is retained. */ }
            }, icon: const Icon(Icons.sync), label: const Text('\u68c0\u67e5\u53d1\u9001\u72b6\u6001')),
            const SizedBox(height: 24),
            Text('\u5f85\u53d1\u9001\uff08${pending.length}\uff09', style: const TextStyle(color: TraceColors.text, fontSize: 18)),
            ...pending.map((item) => _entry(item, sent: false)),
            const SizedBox(height: 24),
            Text('\u5df2\u63d0\u4ea4\uff08${sent.length}\uff09', style: const TextStyle(color: TraceColors.text, fontSize: 18)),
            const Text('\u8fd9\u91cc\u53ea\u8868\u793a\u670d\u52a1\u5668\u5df2\u6536\u5230\uff0c\u4e0d\u4ee3\u8868\u95ee\u9898\u5df2\u5904\u7406\u3002', style: TextStyle(color: TraceColors.muted, fontSize: 12)),
            ...sent.map((item) => _entry(item, sent: true)),
          ]);
        }),
      ))),
    )),
  );
}
