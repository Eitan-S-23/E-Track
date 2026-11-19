import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'trace_ui.dart';

class CompanionDiagnosticSnapshot {
  CompanionDiagnosticSnapshot(this.rows);
  final List<Map<String, Object>> rows;
  static Future<CompanionDiagnosticSnapshot> read() async {
    final value = await const MethodChannel('trace/companion').invokeMapMethod<String, dynamic>('diagnostics');
    final history = value?['history'];
    final rows = <Map<String, Object>>[];
    if (history is List) {
      for (final entry in history.reversed.take(80)) {
        if (entry is! Map) continue;
        final row = <String, Object>{};
        for (final key in ['at', 'uptimeMs', 'attempt', 'elapsedMs', 'errorCode']) {
          final number = entry[key];
          if (number is int && number >= 0 && number <= (key == 'at' ? 8640000000000000 : 9007199254740991)) row[key] = number;
        }
        for (final key in ['state', 'stage', 'trigger', 'errorType', 'errorCode', 'runtime']) {
          final text = entry[key];
          if (text is String && RegExp(r'^[A-Za-z0-9_]{1,64}$').hasMatch(text)) row[key] = text;
        }
        if (row['state'] != null) rows.add(row);
      }
    }
    return CompanionDiagnosticSnapshot(rows);
  }

  String get text => ['E-Track background connection diagnostics (newest first)',
    'Local history only; no addresses, tokens, URLs or payloads.', ...rows.map(line)].join('\n');
  static String line(Map<String, Object> row) {
    final at = row['at'];
    final time = at is int ? DateTime.fromMillisecondsSinceEpoch(at).toLocal().toString().split('.').first : '?';
    return '$time ${row['state']} ${row['stage'] ?? ''} ${row['elapsedMs'] ?? '-'}ms '
        '${row['trigger'] ?? ''} ${row['errorType'] ?? ''} ${row['errorCode'] ?? ''}'.trim();
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
  @override
  void initState() { super.initState(); _snapshot = CompanionDiagnosticSnapshot.read(); }

  @override
  Widget build(BuildContext context) => TraceBackGesture(child: Scaffold(
    backgroundColor: TraceColors.ink,
    appBar: AppBar(backgroundColor: TraceColors.ink, foregroundColor: TraceColors.text,
      title: const Text('\u8fde\u63a5\u8bca\u65ad'),
      leading: IconButton(key: const ValueKey('detail-back'), tooltip: '\u8fd4\u56de',
        onPressed: () => TraceBackGesture.back(context), icon: const Icon(Icons.arrow_back)),
      actions: [IconButton(tooltip: '\u5237\u65b0', onPressed: () => setState(() { _snapshot = CompanionDiagnosticSnapshot.read(); }), icon: const Icon(Icons.refresh))]),
    body: TracePageScaffold(child: SafeArea(child: FutureBuilder<CompanionDiagnosticSnapshot>(
      future: _snapshot, builder: (context, snapshot) {
        final value = snapshot.data;
        return ListView(padding: const EdgeInsets.all(24), children: [
          const Text('\u8bb0\u5f55\u540e\u53f0\u542f\u52a8\u3001\u8fde\u63a5\u3001\u670d\u52a1\u53d1\u73b0\u548c\u8bbe\u5907\u8eab\u4efd\u786e\u8ba4\u3002\u6700\u591a\u4fdd\u7559 80 \u6761\uff0c\u65b0\u8bb0\u5f55\u5728\u524d\u3002\u4ec5\u4fdd\u5b58\u5728\u672c\u673a\uff0c\u4e0d\u81ea\u52a8\u4e0a\u4f20\u65e5\u5fd7\u3002',
            style: TextStyle(color: TraceColors.muted, height: 1.5)),
          const SizedBox(height: 16),
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
        ]);
      },
    ))),
  ));
}

bool get companionDiagnosticsSupported => Platform.isAndroid;
