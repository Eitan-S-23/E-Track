import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'trace_ui.dart';

class CompanionDiagnosticSnapshot {
  CompanionDiagnosticSnapshot(this.rows, {this.metadata = const {}, this.nextCursor});
  final List<Map<String, Object>> rows;
  final Map<String, dynamic> metadata;
  final int? nextCursor;
  static Future<CompanionDiagnosticSnapshot> read({Map<String, Object?> filter = const {}}) async {
    final value = await const MethodChannel('trace/companion').invokeMapMethod<String, dynamic>('diagnostics', filter);
    final history = value?['history'];
    final rows = <Map<String, Object>>[];
    if (history is List) {
      for (final entry in history.take(200)) {
        if (entry is! Map) continue;
        final row = <String, Object>{};
        for (final key in ['at', 'seq', 'count', 'lastAt', 'uptimeMs', 'attempt', 'elapsedMs', 'errorCode',
          'startupWaitMs', 'connectionMs', 'closeToReadyMs', 'lastCheckAt', 'nextCheckAt', 'executedAt', 'retryCount',
          'queueDelayMs', 'heapUsedBytes', 'queuedEvents']) {
          final number = entry[key];
          if (number is int && number >= 0 && number <= (key == 'at' ? 8640000000000000 : 9007199254740991)) row[key] = number;
        }
        for (final key in ['state', 'stage', 'trigger', 'errorType', 'errorCode', 'runtime', 'level',
          'taskId', 'recoveryId', 'deviceKey', 'source', 'outcome', 'reason', 'uiState', 'launchSource',
          'termination', 'reconnection', 'processId']) {
          final text = entry[key];
          if (text is String && RegExp(r'^[A-Za-z0-9_]{1,64}$').hasMatch(text)) row[key] = text;
        }
        if (row['state'] != null) rows.add(row);
      }
    }
    return CompanionDiagnosticSnapshot(rows, metadata: value?['metadata'] is Map
        ? Map<String, dynamic>.from(value!['metadata'] as Map) : {},
        nextCursor: value?['nextCursor'] is int ? value!['nextCursor'] as int : null);
  }

  String get text => ['E-Track background connection diagnostics (newest first)',
    'Local page only; use complete export for the retained journal. Missing timings are unknown.', ...rows.map(line)].join('\n');
  static String line(Map<String, Object> row) {
    final at = row['at'];
    final time = at is int ? DateTime.fromMillisecondsSinceEpoch(at).toLocal().toString().split('.').first : '?';
    return '$time ${row['state']} x${row['count'] ?? 1}\n'
        '${row.entries.where((e) => !['at', 'state', 'count'].contains(e.key)).map((e) => '${e.key}=${e.value}').join(' ')}';
  }
  String excerpt(int maximum) {
    const header = '\n\n[Background connection diagnostics]\n';
    if (maximum < header.length + 100) throw StateError('DIAGNOSTIC_FEEDBACK_TOO_LONG');
    final buffer = StringBuffer(header);
    for (final row in rows.take(8)) {
      final entry = '${line(row)}\n';
      if (buffer.length + entry.length > maximum) break;
      buffer.write(entry);
    }
    if (rows.isEmpty) buffer.write('No recorded connection attempts.\n');
    return buffer.toString();
  }
}

class CompanionDiagnosticsPage extends StatefulWidget {
  const CompanionDiagnosticsPage({super.key});
  @override
  State<CompanionDiagnosticsPage> createState() => _CompanionDiagnosticsPageState();
}

class _CompanionDiagnosticsPageState extends State<CompanionDiagnosticsPage> {
  late Future<CompanionDiagnosticSnapshot> _snapshot;
  final _search = TextEditingController(), _device = TextEditingController(), _task = TextEditingController();
  String _level = '';
  DateTimeRange? _range;
  final List<int?> _cursors = [null];
  Map<String, Object?> get _filter => {'search': _search.text, 'deviceKey': _device.text,
    'taskId': _task.text, 'level': _level, 'beforeSeq': _cursors.last,
    'from': _range?.start.millisecondsSinceEpoch,
    'to': _range?.end.add(const Duration(days: 1)).millisecondsSinceEpoch, 'limit': 80};
  void _refresh({bool reset = true}) => setState(() {
    if (reset) { _cursors.clear(); _cursors.add(null); }
    _snapshot = CompanionDiagnosticSnapshot.read(filter: _filter);
  });
  @override
  void dispose() { _search.dispose(); _device.dispose(); _task.dispose(); super.dispose(); }
  @override
  void initState() { super.initState(); _snapshot = CompanionDiagnosticSnapshot.read(); }

  @override
  Widget build(BuildContext context) => TraceBackGesture(child: Scaffold(
    backgroundColor: TraceColors.ink,
    appBar: AppBar(backgroundColor: TraceColors.ink, foregroundColor: TraceColors.text,
      title: const Text('\u8fde\u63a5\u8bca\u65ad'),
      leading: IconButton(key: const ValueKey('detail-back'), tooltip: '\u8fd4\u56de',
        onPressed: () => TraceBackGesture.back(context), icon: const Icon(Icons.arrow_back)),
      actions: [IconButton(tooltip: '\u5237\u65b0', onPressed: _refresh, icon: const Icon(Icons.refresh))]),
    body: TracePageScaffold(child: SafeArea(child: FutureBuilder<CompanionDiagnosticSnapshot>(
      future: _snapshot, builder: (context, snapshot) {
        final value = snapshot.data;
        return ListView(padding: const EdgeInsets.all(24), children: [
          const Text('最近 7 天，最多 20 MB，仅保存在本机。触发来源不代表界面状态；缺少关闭时刻则总耗时未知。未发生重连会单独标记。系统强制停止可能没有最终回调。',
            style: TextStyle(color: TraceColors.muted, height: 1.5)),
          const SizedBox(height: 16),
          TextField(controller: _search, decoration: const InputDecoration(labelText: '搜索事件 / 阶段 / 错误'), onSubmitted: (_) => _refresh()),
          TextField(controller: _device, decoration: const InputDecoration(labelText: '设备匿名编号（完整 deviceKey）')),
          TextField(controller: _task, decoration: const InputDecoration(labelText: '任务编号')),
          DropdownButton<String>(value: _level, isExpanded: true,
            items: const [DropdownMenuItem(value: '', child: Text('全部级别')), DropdownMenuItem(value: 'error', child: Text('错误')), DropdownMenuItem(value: 'info', child: Text('信息'))],
            onChanged: (value) { _level = value ?? ''; _refresh(); }),
          Wrap(spacing: 8, children: [OutlinedButton(onPressed: _refresh, child: const Text('筛选')),
            OutlinedButton(onPressed: () async {
              final now = DateTime.now();
              final range = await showDateRangePicker(context: context, firstDate: now.subtract(const Duration(days: 7)), lastDate: now);
              if (!mounted || range == null) return;
              _range = range; _refresh();
            }, child: Text(_range == null ? '选择时间' : '已限定时间')),
            OutlinedButton(onPressed: () { _range = null; _search.clear(); _device.clear(); _task.clear(); _level = ''; _refresh(); }, child: const Text('重置筛选'))]),
          OutlinedButton.icon(onPressed: () async {
            try {
              await const MethodChannel('trace/companion').invokeMethod<Object?>('diagnosticExport');
            } catch (_) { if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('导出失败，原日志仍保留'))); }
          }, icon: const Icon(Icons.ios_share), label: const Text('完整导出：可读日志 + JSONL + 缺失说明')),
          OutlinedButton(onPressed: () async {
            try { await const MethodChannel('trace/companion').invokeMethod<Object?>('diagnosticDetail', {'minutes': 15}); }
            catch (_) { return; }
            if (mounted) _refresh();
          }, child: const Text('开启有界详细诊断（15 分钟 / 2000 事件）')),
          TextButton(onPressed: () async {
            try { await const MethodChannel('trace/companion').invokeMethod<Object?>('diagnosticDetail', {'minutes': 0}); }
            catch (_) { return; }
            if (mounted) _refresh();
          }, child: const Text('关闭详细诊断')),
          if (snapshot.connectionState != ConnectionState.done) const LinearProgressIndicator(),
          if (snapshot.hasError) const Text('\u6682\u65f6\u65e0\u6cd5\u8bfb\u53d6\u8bca\u65ad\u8bb0\u5f55\uff0c\u8bf7\u5237\u65b0\u91cd\u8bd5\u3002', style: TextStyle(color: TraceColors.amber)),
          if (value != null) OutlinedButton.icon(key: const ValueKey('copy-connection-diagnostics'),
            onPressed: () async {
              await Clipboard.setData(ClipboardData(text: value.text));
              if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('\u8bca\u65ad\u8bb0\u5f55\u5df2\u590d\u5236')));
            }, icon: const Icon(Icons.copy_outlined), label: const Text('\u590d\u5236\u8bca\u65ad\u8bb0\u5f55')),
          if (value?.rows.isEmpty == true) const Text('\u6682\u65e0\u8fde\u63a5\u8bb0\u5f55\u3002\u8bf7\u5728\u95ee\u9898\u590d\u73b0\u540e\u518d\u67e5\u770b\u3002', style: TextStyle(color: TraceColors.muted)),
          if (value != null) ...value.rows.map((row) => Padding(padding: const EdgeInsets.symmetric(vertical: 10),
            child: SelectableText(CompanionDiagnosticSnapshot.line(row), style: const TextStyle(color: TraceColors.text, height: 1.5)))),
          if (value != null) Text('保留 ${value.metadata['retainedBytes'] ?? '?'} B；淘汰 ${value.metadata['prunedBytes'] ?? '?'} B；'
            '丢弃 ${value.metadata['droppedEvents'] ?? '?'}；写入错误 ${value.metadata['ioErrors'] ?? '?'}；'
            '损坏行 ${value.metadata['malformedLines'] ?? '?'}；进程终止缺失未知', style: const TextStyle(color: TraceColors.muted)),
          Wrap(spacing: 8, children: [if (_cursors.length > 1) OutlinedButton(onPressed: () {
            _cursors.removeLast(); _refresh(reset: false);
          }, child: const Text('上一页')), if (value?.nextCursor != null) OutlinedButton(onPressed: () {
            _cursors.add(value!.nextCursor); _refresh(reset: false);
          }, child: const Text('下一页'))]),
        ]);
      },
    ))),
  ));
}

bool get companionDiagnosticsSupported => Platform.isAndroid;
