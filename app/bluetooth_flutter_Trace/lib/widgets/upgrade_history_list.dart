import 'dart:math' as math;
import 'package:flutter/material.dart';

/// Passes unconsumed drag distance to the page without ending the gesture.
class ChainedScrollController extends ScrollController {
  ChainedScrollController(this.outer);
  final ScrollController outer;
  @override
  ScrollPosition createScrollPosition(ScrollPhysics physics, ScrollContext context,
      ScrollPosition? oldPosition) => _ChainedPosition(
        physics: physics, context: context, oldPosition: oldPosition, outer: outer);
}

class _ChainedPosition extends ScrollPositionWithSingleContext {
  _ChainedPosition({required super.physics, required super.context,
    super.oldPosition, required this.outer});
  final ScrollController outer;

  @override
  void applyUserOffset(double delta) {
    final target = (pixels - delta).clamp(minScrollExtent, maxScrollExtent);
    final used = pixels - target;
    if (used != 0) super.applyUserOffset(used);
    final remainder = delta - used;
    if (remainder != 0 && outer.hasClients) {
      final parent = outer.position;
      if (parent is ScrollPositionWithSingleContext) parent.applyUserOffset(remainder);
    }
  }

  @override
  void pointerScroll(double delta) {
    final used = (pixels + delta).clamp(minScrollExtent, maxScrollExtent) - pixels;
    if (used != 0) super.pointerScroll(used);
    if (delta != used && outer.hasClients) outer.position.pointerScroll(delta - used);
  }
}

class UpgradeHistoryList extends StatefulWidget {
  const UpgradeHistoryList({super.key, required this.records, required this.outer});
  final List<Map<String, dynamic>> records;
  final ScrollController outer;
  @override
  State<UpgradeHistoryList> createState() => _UpgradeHistoryListState();
}

class _UpgradeHistoryListState extends State<UpgradeHistoryList> {
  late final controller = ChainedScrollController(widget.outer);
  @override
  void dispose() { controller.dispose(); super.dispose(); }

  String version(Object? value) => value is int
      ? '${value ~/ 10000}.${value ~/ 100 % 100}.${value % 100}' : '未知';
  String time(Object? value) => value is int
      ? DateTime.fromMillisecondsSinceEpoch(value).toLocal().toString().split('.').first : '未知';
  String result(Map<String, dynamic> row) => switch (row['status']) {
    'success' => '成功', 'cancelled' => '已取消',
    'awaitingVerification' => '等待核验', 'running' => '进行中', _ => '失败',
  };

  void details(Map<String, dynamic> row) {
    final duration = row['durationMs'];
    final kind = switch (row['kind']) { 'patch' => '差分', 'full' => '全量', _ => '未知' };
    showDialog<void>(context: context, builder: (context) => AlertDialog(
      title: const Text('升级记录详情'),
      content: SingleChildScrollView(child: SelectableText([
        '结果：${result(row)}',
        '版本：${version(row['beforeVersion'])} → ${version(row['targetVersion'])}',
        '核验后版本：${version(row['afterVersion'])}',
        '开始：${time(row['startedAt'])}', '核验：${time(row['verifiedAt'])}',
        '包类型：$kind',
        '发起方式：${row['initiator'] == 'mcu' ? '设备' : row['initiator'] == 'app' ? 'APP' : '未知'}',
        '耗时：${duration is int ? '${(duration / 1000).toStringAsFixed(1)} 秒' : '未知'}',
        '阶段：${row['stage'] ?? '未知'}', '错误码：${row['errorCode'] ?? '无'}',
        '重试次数：${row['retryCount'] ?? '未知'}', '任务：${row['taskId'] ?? '未知'}',
        '设备：${row['device'] ?? '未知'}', '设备标识：${row['deviceKey'] ?? '未知'}',
        '包 SHA-256：${row['packageSha'] ?? '未知'}',
        '目标 SHA-256：${row['targetSha'] ?? '未知'}',
        '核验 SHA-256：${row['afterSha'] ?? '未知'}',
      ].join('\n\n'))),
      actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('关闭'))],
    ));
  }

  @override
  Widget build(BuildContext context) {
    final rowHeight = math.max(80.0, MediaQuery.textScalerOf(context).scale(64));
    final height = math.min(widget.records.length * rowHeight,
        math.min(rowHeight * 3.5, MediaQuery.sizeOf(context).height * .45));
    return SizedBox(height: height, child: ListView.builder(
      key: const ValueKey('upgrade-history-window'),
      controller: controller, primary: false, padding: EdgeInsets.zero,
      physics: const AlwaysScrollableScrollPhysics(parent: ClampingScrollPhysics()),
      itemExtent: rowHeight, itemCount: widget.records.length,
      itemBuilder: (context, index) {
        final row = widget.records[index];
        final color = row['status'] == 'success' ? Colors.green
            : ['running', 'awaitingVerification'].contains(row['status']) ? Colors.orange : Colors.red;
        return ListTile(
          key: ValueKey('upgrade-history-${row['taskId']}'), contentPadding: EdgeInsets.zero,
          title: Text('${version(row['beforeVersion'])} → ${version(row['targetVersion'])}',
            maxLines: 1, overflow: TextOverflow.ellipsis),
          subtitle: Text(time(row['startedAt']), maxLines: 1, overflow: TextOverflow.ellipsis),
          trailing: Text(result(row), style: TextStyle(color: color, fontSize: 12)),
          onTap: () => details(row),
        );
      },
    ));
  }
}
