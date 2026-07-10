import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:get/get.dart';
import '../services/app_update_service.dart';
import '../services/database_service.dart';
import 'trace_ui.dart';

const String _appName = 'BLE Monitor';
const MethodChannel _appUpdateChannel = MethodChannel('trace/app_update');
final Future<String> _appVersionLabelFuture = _loadAppVersionLabel();

Future<String> _loadAppVersionLabel() async {
  try {
    final result =
        await _appUpdateChannel.invokeMapMethod<String, dynamic>('getAppInfo');
    final versionName = result?['versionName']?.toString().trim() ?? '';
    if (versionName.isNotEmpty) {
      return '$_appName v$versionName';
    }
  } catch (_) {
    // Keep the profile usable on platforms without the Android update channel.
  }

  return _appName;
}

class ProfileTabPage extends StatelessWidget {
  const ProfileTabPage({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return TracePageScaffold(
      paintBackground: false,
      child: SafeArea(
        bottom: false,
        child: SingleChildScrollView(
          physics: const BouncingScrollPhysics(),
          padding: const EdgeInsets.fromLTRB(
            14,
            36,
            14,
            TraceTheme.pageBottomPadding,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const _ProfileTitle(),
                  const Spacer(),
                  _ProfileAvatar(onTap: _showUserInfoDialog),
                ],
              ).animate().fadeIn(duration: 420.ms).slideY(begin: 0.14, end: 0),
              const SizedBox(height: 30),
              _ProfilePanel(
                versionHeader: _buildVersionText(
                  style: const TextStyle(
                    color: TraceColors.text,
                    fontSize: 18,
                    fontWeight: FontWeight.w800,
                    letterSpacing: 0.4,
                  ),
                ),
                actions: _buildActions(),
              )
                  .animate(delay: 100.ms)
                  .fadeIn(duration: 520.ms)
                  .slideY(begin: 0.08, end: 0),
              const SizedBox(height: 24),
              const _ProfileFooter()
                  .animate(delay: 220.ms)
                  .fadeIn(duration: 480.ms),
            ],
          ),
        ),
      ),
    );
  }

  List<_ProfileAction> _buildActions() {
    return [
      _ProfileAction(
        label: '数据统计',
        icon: Icons.bar_chart,
        onTap: _showDataStatistics,
      ),
      _ProfileAction(
        label: '应用设置',
        icon: Icons.settings,
        onTap: _showSettingsDialog,
      ),
      _ProfileAction(
        label: '检查更新',
        icon: Icons.autorenew,
        onTap: _checkForUpdates,
      ),
      _ProfileAction(
        label: '帮助与反馈',
        icon: Icons.chat_bubble_outline,
        onTap: _showHelpDialog,
      ),
      _ProfileAction(
        label: '关于应用',
        icon: Icons.info_outline,
        onTap: _showAboutDialog,
      ),
    ];
  }

  Widget _buildVersionText({TextStyle? style}) {
    return FutureBuilder<String>(
      future: _appVersionLabelFuture,
      builder: (context, snapshot) {
        return Text(
          snapshot.data ?? _appName,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: style,
        );
      },
    );
  }

  void _checkForUpdates() {
    final service = Get.isRegistered<AppUpdateService>()
        ? AppUpdateService.to
        : Get.put(AppUpdateService(), permanent: true);
    unawaited(service.checkForUpdates());
  }

  void _showSettingsDialog() {
    _showTraceDialog(
      TraceDialog(
        title: '应用设置',
        icon: Icons.settings,
        color: TraceColors.mint,
        message: '设置功能开发中。当前版本先保留入口，后续会接入个性化配置。',
        actions: [
          TraceDialogAction(
            label: '知道了',
            isPrimary: true,
            color: TraceColors.mint,
            onPressed: TraceDialog.close,
          ),
        ],
      ),
    );
  }

  void _showUserInfoDialog() {
    _showTraceDialog(
      TraceDialog(
        title: '用户信息',
        icon: Icons.person_outline,
        color: TraceColors.cyan,
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _buildUserInfoRow('身份', '智能设备用户'),
            const SizedBox(height: 10),
            FutureBuilder<String>(
              future: _appVersionLabelFuture,
              builder: (context, snapshot) {
                return _buildUserInfoRow(
                  '应用',
                  snapshot.data ?? _appName,
                );
              },
            ),
            const SizedBox(height: 10),
            _buildUserInfoRow('数据', '设备与骑行记录保存在本机'),
          ],
        ),
        actions: [
          TraceDialogAction(
            label: '确定',
            isPrimary: true,
            color: TraceColors.cyan,
            onPressed: TraceDialog.close,
          ),
        ],
      ),
    );
  }

  void _showDataStatistics() async {
    try {
      final dbService = DatabaseService();
      final dbInfo = await dbService.getDatabaseInfo();

      _showTraceDialog(
        TraceDialog(
          title: '数据统计',
          icon: Icons.bar_chart,
          color: TraceColors.cyan,
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              _buildStatItem('保存的设备', '${dbInfo['deviceCount']} 个'),
              const SizedBox(height: 10),
              _buildStatItem('数据记录', '${dbInfo['dataCount']} 条'),
            ],
          ),
          actions: [
            TraceDialogAction(
              label: '确定',
              isPrimary: true,
              onPressed: TraceDialog.close,
            ),
          ],
        ),
      );
    } catch (e) {
      Get.snackbar('错误', '获取数据统计失败: $e');
    }
  }

  Widget _buildStatItem(String label, String value) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(label),
        Text(
          value,
          style: const TextStyle(
            fontWeight: FontWeight.w900,
            color: TraceColors.cyan,
          ),
        ),
      ],
    );
  }

  Widget _buildUserInfoRow(String label, String value) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          width: 52,
          child: Text(
            label,
            style: TextStyle(
              color: TraceColors.text.withOpacity(0.74),
              fontWeight: FontWeight.w800,
            ),
          ),
        ),
        Expanded(
          child: Text(
            value,
            style: const TextStyle(
              color: TraceColors.cyanSoft,
              fontWeight: FontWeight.w900,
            ),
          ),
        ),
      ],
    );
  }

  void _showHelpDialog() {
    _showTraceDialog(
      TraceDialog(
        title: '帮助与反馈',
        icon: Icons.chat_bubble_outline,
        color: TraceColors.amber,
        content: const Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('功率计功能：'),
            Text('1. 扫描并选择 BLE 设备'),
            Text('2. 点击监控查看实时数据'),
            Text('3. 保存设备以便长期监控'),
            SizedBox(height: 16),
            Text('码表功能：'),
            Text('1. 连接码表设备'),
            Text('2. 查看骑行数据'),
            Text('3. OTA 升级固件'),
            SizedBox(height: 16),
            Text('遥控功能：'),
            Text('1. 连接蓝牙设备'),
            Text('2. 自定义控制按钮'),
            Text('3. 发送控制指令'),
          ],
        ),
        actions: [
          TraceDialogAction(
            label: '确定',
            isPrimary: true,
            color: TraceColors.amber,
            onPressed: TraceDialog.close,
          ),
        ],
      ),
    );
  }

  void _showAboutDialog() {
    _showTraceDialog(
      TraceDialog(
        title: '关于应用',
        icon: Icons.info_outline,
        color: TraceColors.rose,
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _buildVersionText(),
            const SizedBox(height: 8),
            const Text('智能蓝牙设备管理助手'),
            const SizedBox(height: 16),
            const Text('功能特性：'),
            const Text('• 功率计监控'),
            const Text('• 码表数据管理'),
            const Text('• 遥控设备控制'),
            const Text('• 数据可视化'),
            const Text('• OTA 固件升级'),
          ],
        ),
        actions: [
          TraceDialogAction(
            label: '确定',
            isPrimary: true,
            color: TraceColors.rose,
            onPressed: TraceDialog.close,
          ),
        ],
      ),
    );
  }

  void _showTraceDialog(TraceDialog dialog) {
    Get.dialog<void>(
      dialog,
      barrierColor: Colors.black.withOpacity(0.62),
    );
  }
}

class _ProfileAction {
  const _ProfileAction({
    required this.label,
    required this.icon,
    required this.onTap,
  });

  final String label;
  final IconData icon;
  final VoidCallback onTap;
}

class _ProfileTitle extends StatelessWidget {
  const _ProfileTitle();

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: 36, left: 4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            '我的',
            style: TextStyle(
              color: TraceColors.text,
              fontSize: 46,
              height: 1,
              fontWeight: FontWeight.w900,
              letterSpacing: 3,
              shadows: [
                Shadow(color: Color(0xAA24F6DE), blurRadius: 24),
                Shadow(color: Color(0x5524F6DE), blurRadius: 44),
              ],
            ),
          ),
          const SizedBox(height: 14),
          SizedBox(
            width: 142,
            child: Row(
              children: [
                Expanded(child: _profileTitleLine()),
                const SizedBox(width: 6),
                _profileTitleDot(TraceColors.cyan),
                const SizedBox(width: 18),
                _profileTitleDot(TraceColors.cyan.withOpacity(0.7)),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _profileTitleLine() {
    return Container(
      height: 1.4,
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            TraceColors.cyan.withOpacity(0.9),
            Colors.transparent,
          ],
        ),
        boxShadow: [
          BoxShadow(
            color: TraceColors.cyan.withOpacity(0.55),
            blurRadius: 9,
          ),
        ],
      ),
    );
  }

  Widget _profileTitleDot(Color color) {
    return Container(
      width: 4,
      height: 4,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: color,
        boxShadow: [
          BoxShadow(color: color.withOpacity(0.8), blurRadius: 8),
        ],
      ),
    );
  }
}

/// 右上角发光头像与身份标签
class _ProfileAvatar extends StatelessWidget {
  const _ProfileAvatar({required this.onTap});

  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        SizedBox(
          width: 118,
          height: 118,
          child: Stack(
            alignment: Alignment.center,
            children: [
              CustomPaint(
                size: const Size.square(118),
                painter: _ProfileAvatarDialPainter(),
              ),
              Semantics(
                button: true,
                label: '查看用户信息',
                child: Material(
                  color: Colors.transparent,
                  shape: const CircleBorder(),
                  child: InkWell(
                    onTap: onTap,
                    customBorder: const CircleBorder(),
                    splashColor: TraceColors.cyan.withOpacity(0.18),
                    highlightColor: TraceColors.cyan.withOpacity(0.08),
                    child: Ink(
                      width: 82,
                      height: 82,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        gradient: RadialGradient(
                          colors: [
                            TraceColors.cyan.withOpacity(0.2),
                            const Color(0xFF06202A).withOpacity(0.96),
                          ],
                        ),
                        border: Border.all(
                          color: TraceColors.cyan.withOpacity(0.9),
                          width: 1.8,
                        ),
                        boxShadow: [
                          BoxShadow(
                            color: TraceColors.cyan.withOpacity(0.45),
                            blurRadius: 28,
                            spreadRadius: -2,
                          ),
                        ],
                      ),
                      child: const Icon(
                        Icons.person_outline,
                        color: TraceColors.cyanSoft,
                        size: 44,
                        shadows: [
                          Shadow(color: Color(0xAA24F6DE), blurRadius: 14),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 4),
        const Text(
          '智能设备用户',
          style: TextStyle(
            color: TraceColors.text,
            fontSize: 17,
            fontWeight: FontWeight.w900,
            letterSpacing: 1,
            shadows: [
              Shadow(color: Color(0x6624F6DE), blurRadius: 12),
            ],
          ),
        ),
      ],
    );
  }
}

class _ProfileAvatarDialPainter extends CustomPainter {
  const _ProfileAvatarDialPainter();

  @override
  void paint(Canvas canvas, Size size) {
    final center = size.center(Offset.zero);
    final radius = size.shortestSide / 2;
    final ringPaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1
      ..color = TraceColors.cyan.withOpacity(0.15);
    canvas.drawCircle(center, radius * 0.96, ringPaint);
    canvas.drawCircle(center, radius * 0.82, ringPaint..color = TraceColors.cyan.withOpacity(0.2));
    canvas.drawCircle(center, radius * 0.66, ringPaint..color = TraceColors.cyan.withOpacity(0.12));

    final arcPaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 4
      ..strokeCap = StrokeCap.round
      ..color = TraceColors.cyan.withOpacity(0.7);
    canvas.drawArc(
      Rect.fromCircle(center: center, radius: radius * 0.9),
      -math.pi * 0.92,
      math.pi * 0.55,
      false,
      arcPaint,
    );
  }

  @override
  bool shouldRepaint(covariant _ProfileAvatarDialPainter oldDelegate) => false;
}

/// 中央功能面板：版本头 + 2+3 圆形功能网格
class _ProfilePanel extends StatelessWidget {
  const _ProfilePanel({
    required this.versionHeader,
    required this.actions,
  }) : assert(actions.length == 5);

  final Widget versionHeader;
  final List<_ProfileAction> actions;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final width = constraints.maxWidth;
        final innerWidth = math.max(0.0, width - 44);
        final topNode = math.min(innerWidth / 2.72, 104.0);
        final bottomNode = math.min(innerWidth / 4.08, 84.0);

        return Stack(
          clipBehavior: Clip.none,
          children: [
            Positioned.fill(
              child: CustomPaint(painter: _ProfilePanelPainter()),
            ),
            ClipPath(
              clipper: _ProfilePanelClipper(),
              child: Container(
                width: double.infinity,
                padding: const EdgeInsets.fromLTRB(22, 30, 22, 38),
                decoration: BoxDecoration(
                  color: const Color(0xFF071B25).withOpacity(0.76),
                  boxShadow: [
                    BoxShadow(
                      color: Colors.black.withOpacity(0.42),
                      blurRadius: 32,
                      offset: const Offset(0, 16),
                    ),
                  ],
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Container(
                          width: 3,
                          height: 22,
                          decoration: BoxDecoration(
                            color: TraceColors.amber,
                            boxShadow: [
                              BoxShadow(
                                color: TraceColors.amber.withOpacity(0.7),
                                blurRadius: 8,
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(child: versionHeader),
                      ],
                    ),
                    const SizedBox(height: 32),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        for (final action in actions.sublist(0, 2))
                          TraceGlowNode(
                            size: topNode,
                            icon: action.icon,
                            label: action.label,
                            labelWidth: 120,
                            onTap: action.onTap,
                          ),
                      ],
                    ),
                    const SizedBox(height: 22),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        for (final action in actions.sublist(2))
                          TraceGlowNode(
                            size: bottomNode,
                            icon: action.icon,
                            label: action.label,
                            labelWidth: 98,
                            onTap: action.onTap,
                          ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
            Positioned(
              top: 1,
              left: width * 0.38,
              right: width * 0.38,
              child: Container(
                height: 3,
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    colors: [
                      Colors.transparent,
                      TraceColors.cyan.withOpacity(0.95),
                      Colors.transparent,
                    ],
                  ),
                  boxShadow: [
                    BoxShadow(
                      color: TraceColors.cyan.withOpacity(0.65),
                      blurRadius: 10,
                    ),
                  ],
                ),
              ),
            ),
          ],
        );
      },
    );
  }
}

class _ProfilePanelClipper extends CustomClipper<Path> {
  @override
  Path getClip(Size size) {
    const cut = 26.0;
    const notch = 42.0;
    return Path()
      ..moveTo(cut, 0)
      ..lineTo(size.width * 0.48, 0)
      ..lineTo(size.width * 0.52, notch * 0.45)
      ..lineTo(size.width - cut, notch * 0.45)
      ..lineTo(size.width, cut)
      ..lineTo(size.width, size.height - cut)
      ..lineTo(size.width - cut, size.height)
      ..lineTo(cut, size.height)
      ..lineTo(0, size.height - cut)
      ..lineTo(0, cut)
      ..close();
  }

  @override
  bool shouldReclip(covariant _ProfilePanelClipper oldClipper) => false;
}

class _ProfilePanelPainter extends CustomPainter {
  const _ProfilePanelPainter();

  @override
  void paint(Canvas canvas, Size size) {
    final path = _ProfilePanelClipper().getClip(size);
    final fillPaint = Paint()
      ..shader = LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [
          TraceColors.cyan.withOpacity(0.18),
          Colors.transparent,
          TraceColors.cyan.withOpacity(0.1),
        ],
      ).createShader(Offset.zero & size);
    canvas.drawPath(path, fillPaint);

    final borderPaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.5
      ..color = TraceColors.cyan.withOpacity(0.62);
    canvas.drawPath(path, borderPaint);

    final glowPaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 5
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 8)
      ..color = TraceColors.cyan.withOpacity(0.28);
    canvas.drawPath(path, glowPaint);

    final sidePaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1
      ..color = TraceColors.cyan.withOpacity(0.22);
    canvas.drawLine(Offset(14, size.height * 0.2), Offset(14, size.height * 0.78), sidePaint);
    canvas.drawLine(
      Offset(size.width - 14, size.height * 0.2),
      Offset(size.width - 14, size.height * 0.78),
      sidePaint,
    );
  }

  @override
  bool shouldRepaint(covariant _ProfilePanelPainter oldDelegate) => false;
}

/// 面板下方标语与装饰
class _ProfileFooter extends StatelessWidget {
  const _ProfileFooter();

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Row(
          children: [
            Expanded(child: _buildFadeLine(reverse: false)),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12),
              child: Text(
                'BLE Monitor 智能设备管理助手',
                style: TextStyle(
                  color: TraceColors.muted.withOpacity(0.85),
                  fontSize: 11.5,
                  fontWeight: FontWeight.w600,
                  letterSpacing: 1,
                ),
              ),
            ),
            Expanded(child: _buildFadeLine(reverse: true)),
          ],
        ),
        const SizedBox(height: 12),
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            for (final opacity in [0.25, 0.8, 0.25])
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 4),
                child: Container(
                  width: 4,
                  height: 4,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: TraceColors.cyan.withOpacity(opacity),
                  ),
                ),
              ),
          ],
        ),
      ],
    );
  }

  Widget _buildFadeLine({required bool reverse}) {
    return Container(
      height: 1,
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: reverse ? Alignment.centerRight : Alignment.centerLeft,
          end: reverse ? Alignment.centerLeft : Alignment.centerRight,
          colors: [
            Colors.transparent,
            TraceColors.cyan.withOpacity(0.45),
          ],
        ),
      ),
    );
  }
}
