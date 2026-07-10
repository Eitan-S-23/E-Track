import 'dart:async';
import 'dart:math' as math;

import 'package:audioplayers/audioplayers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:get/get.dart';
import 'power_meter_page.dart';
import 'remote_control_page.dart';
import 'speedometer_page.dart';
import 'trace_ui.dart';

class DeviceOrbitInteractionNotification extends Notification {
  const DeviceOrbitInteractionNotification(this.active);

  final bool active;
}

class DeviceTabPage extends StatelessWidget {
  const DeviceTabPage({super.key});

  @override
  Widget build(BuildContext context) {
    return TracePageScaffold(
      paintBackground: false,
      child: SafeArea(
        bottom: false,
        child: LayoutBuilder(
          builder: (context, constraints) {
            final compact = constraints.maxHeight < 720;
            final stageWidth = math.min(
              math.max(0.0, constraints.maxWidth - 8),
              420.0,
            );

            return SingleChildScrollView(
              physics: const BouncingScrollPhysics(),
              padding: EdgeInsets.fromLTRB(
                0,
                compact ? 16 : 30,
                0,
                TraceTheme.pageBottomPadding,
              ),
              child: Column(
                children: [
                  const _DeviceTitle()
                      .animate()
                      .fadeIn(duration: 420.ms)
                      .slideY(begin: 0.14, end: 0),
                  SizedBox(height: compact ? 12 : 18),
                  Text(
                    '连接、监控、控制您的蓝牙设备',
                    style: TextStyle(
                      color: TraceColors.cyanSoft.withOpacity(0.86),
                      fontSize: compact ? 16 : 18,
                      fontWeight: FontWeight.w800,
                      letterSpacing: 2.2,
                    ),
                  )
                      .animate(delay: 60.ms)
                      .fadeIn(duration: 420.ms)
                      .slideY(begin: 0.2, end: 0),
                  SizedBox(height: compact ? 18 : 26),
                  Center(
                    child: _DeviceStage(width: stageWidth),
                  )
                      .animate(delay: 120.ms)
                      .fadeIn(duration: 520.ms)
                      .scale(
                        begin: const Offset(0.96, 0.96),
                        end: const Offset(1, 1),
                      ),
                ],
              ),
            );
          },
        ),
      ),
    );
  }
}

class _DeviceTitle extends StatelessWidget {
  const _DeviceTitle();

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 78,
      child: Stack(
        alignment: Alignment.center,
        children: [
          Positioned(
            left: 58,
            right: 58,
            top: 42,
            child: Row(
              children: [
                Expanded(child: _titleBeam(reverse: false)),
                const SizedBox(width: 174),
                Expanded(child: _titleBeam(reverse: true)),
              ],
            ),
          ),
          const Text(
            '设备',
            style: TextStyle(
              color: TraceColors.text,
              fontSize: 54,
              height: 1,
              fontWeight: FontWeight.w900,
              letterSpacing: 8,
              shadows: [
                Shadow(color: Color(0xAA24F6DE), blurRadius: 24),
                Shadow(color: Color(0x6624F6DE), blurRadius: 42),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _titleBeam({required bool reverse}) {
    return Container(
      height: 2,
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: reverse ? Alignment.centerRight : Alignment.centerLeft,
          end: reverse ? Alignment.centerLeft : Alignment.centerRight,
          colors: [
            Colors.transparent,
            TraceColors.cyan.withOpacity(0.9),
          ],
        ),
        boxShadow: [
          BoxShadow(
            color: TraceColors.cyan.withOpacity(0.55),
            blurRadius: 10,
          ),
        ],
      ),
    );
  }
}

class _DeviceStage extends StatefulWidget {
  const _DeviceStage({required this.width});

  final double width;

  @override
  State<_DeviceStage> createState() => _DeviceStageState();
}

class _DeviceStageState extends State<_DeviceStage>
    with SingleTickerProviderStateMixin {
  static const Duration _vaultRotateSinglePlayDuration =
      Duration(seconds: 3);

  late final AnimationController _settleController;
  late final AudioPlayer _gearPlayer;
  Animation<double>? _settleAnimation;
  double _rotation = 0;
  double _dragStartAngle = 0;
  double _dragStartRotation = 0;
  double _lastDragAngle = 0;
  double _dragAngularVelocity = 0;
  double _dragTravel = 0;
  bool _rotationGestureActive = false;
  DateTime? _lastDragAt;
  Offset? _lastDragPosition;
  bool _gearSoundActive = false;
  double _orbitGlowDirection = 1;
  double _orbitGlowIntensity = 0;
  double _settleGlowBaseIntensity = 0;

  @override
  void initState() {
    super.initState();
    _settleController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 720),
    )..addListener(() {
        final animation = _settleAnimation;
        if (animation == null) return;
        final fade = 1 - _settleController.value;
        setState(() {
          _rotation = animation.value;
          _orbitGlowIntensity =
              (_settleGlowBaseIntensity * (0.36 + fade * 0.64))
                  .clamp(0.18, 1.0);
        });
      })
      ..addStatusListener((status) {
        if (status == AnimationStatus.completed) {
          setState(() {
            _orbitGlowIntensity = 0;
            _settleGlowBaseIntensity = 0;
          });
          _stopGearSound();
        }
      });
    _gearPlayer = AudioPlayer(playerId: 'device-orbit-gear');
    unawaited(_gearPlayer.setReleaseMode(ReleaseMode.loop));
    unawaited(_gearPlayer.setPlayerMode(PlayerMode.lowLatency));
  }

  @override
  void dispose() {
    _settleController.dispose();
    unawaited(_gearPlayer.dispose());
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final geometry = _DeviceStageGeometry(
      widget.width,
      rotation: _rotation,
    );
    final actions = _buildActions();
    final coreTouchSize = geometry.coreSize * 1.18;

    return SizedBox(
      width: geometry.width,
      height: geometry.height,
      child: Stack(
        clipBehavior: Clip.none,
        children: [
          Positioned.fill(
            child: CustomPaint(
              painter: _DeviceStagePainter(
                geometry,
                orbitGlowDirection: _orbitGlowDirection,
                orbitGlowIntensity: _orbitGlowIntensity,
              ),
            ),
          ),
          for (var i = 0; i < actions.length; i++)
            Builder(
              builder: (context) {
                final nodeOrigin = Offset(
                  geometry.satellites[i].dx - geometry.nodeSize * 0.68,
                  geometry.satellites[i].dy - geometry.nodeSize * 0.68,
                );
                return Positioned(
                  left: nodeOrigin.dx,
                  top: nodeOrigin.dy,
                  child: GestureDetector(
                    behavior: HitTestBehavior.translucent,
                    onPanDown: (details) => _startRotation(
                      nodeOrigin + details.localPosition,
                      geometry.core,
                    ),
                    onPanUpdate: (details) => _updateRotation(
                      nodeOrigin + details.localPosition,
                      geometry.core,
                    ),
                    onPanEnd: (_) => _finishRotation(),
                    onPanCancel: _finishRotation,
                    child: TraceGlowNode(
                      size: geometry.nodeSize,
                      icon: actions[i].icon,
                      semanticLabel: actions[i].title,
                      onTap: actions[i].onTap,
                    ),
                  ),
                );
              },
            ),
          for (var i = 0; i < actions.length; i++)
            Positioned(
              left: geometry.labels[i].left,
              top: geometry.labels[i].top,
              width: geometry.labels[i].width,
              child: _DeviceNodeLabel(
                title: actions[i].title,
                alignment: geometry.labels[i].alignment,
                onTap: actions[i].onTap,
              ),
            ),
          Positioned(
            left: geometry.core.dx - coreTouchSize / 2,
            top: geometry.core.dy - coreTouchSize / 2,
            child: GestureDetector(
              behavior: HitTestBehavior.opaque,
              onPanDown: (details) => _startRotation(
                geometry.core -
                    Offset(coreTouchSize / 2, coreTouchSize / 2) +
                    details.localPosition,
                geometry.core,
              ),
              onPanUpdate: (details) => _updateRotation(
                geometry.core -
                    Offset(coreTouchSize / 2, coreTouchSize / 2) +
                    details.localPosition,
                geometry.core,
              ),
              onPanEnd: (_) => _finishRotation(),
              onPanCancel: _finishRotation,
              child: SizedBox.square(
                dimension: coreTouchSize,
                child: Center(child: _DeviceCore(size: geometry.coreSize)),
              ),
            ),
          ),
        ],
      ),
    );
  }

  void _startRotation(Offset stagePosition, Offset core) {
    if (_rotationGestureActive) return;
    _rotationGestureActive = true;
    _settleController.stop();
    _dragStartAngle = _angleFromStagePosition(stagePosition, core);
    _dragStartRotation = _rotation;
    _lastDragAngle = _dragStartAngle;
    _dragAngularVelocity = 0;
    _dragTravel = 0;
    _lastDragAt = DateTime.now();
    _lastDragPosition = stagePosition;
    _orbitGlowIntensity = 0;
    _settleGlowBaseIntensity = 0;
    _notifyOrbitInteraction(active: true);
  }

  void _updateRotation(Offset stagePosition, Offset core) {
    if (!_rotationGestureActive) return;
    final now = DateTime.now();
    final currentAngle = _angleFromStagePosition(stagePosition, core);
    final delta = _normalizeAngle(currentAngle - _lastDragAngle);
    final lastAt = _lastDragAt;
    if (lastAt != null) {
      final seconds = now.difference(lastAt).inMicroseconds / 1000000;
      if (seconds > 0) {
        final velocity = delta / seconds;
        _dragAngularVelocity = _dragAngularVelocity == 0
            ? velocity
            : _dragAngularVelocity * 0.72 + velocity * 0.28;
      }
    }
    final lastPosition = _lastDragPosition;
    if (lastPosition != null) {
      _dragTravel += (stagePosition - lastPosition).distance;
    }
    _lastDragAngle = currentAngle;
    _lastDragAt = now;
    _lastDragPosition = stagePosition;
    if (delta.abs() > 0.002) {
      _orbitGlowDirection = delta.sign;
      final speedGlow = (_dragAngularVelocity.abs() / 10).clamp(0.0, 0.45);
      final travelGlow = (_dragTravel / (widget.width * 0.9)).clamp(0.0, 0.35);
      _orbitGlowIntensity = (0.38 + speedGlow + travelGlow).clamp(0.38, 1.0);
      _startGearSound();
    }
    setState(() => _rotation += delta);
  }

  void _finishRotation() {
    if (!_rotationGestureActive) return;
    _rotationGestureActive = false;
    _notifyOrbitInteraction(active: false);
    _settleRotation(
      throwVelocity: _dragAngularVelocity,
      throwDistance: _dragTravel,
    );
    _lastDragAt = null;
    _lastDragPosition = null;
  }

  void _settleRotation({
    double throwVelocity = 0,
    double throwDistance = 0,
  }) {
    final step = math.pi / 2;
    final dragDelta = _normalizeAngle(_rotation - _dragStartRotation);
    final moved = dragDelta.abs() > 0.01 ||
        throwVelocity.abs() > 0.08 ||
        throwDistance > widget.width * 0.025;
    final rawDirection = throwVelocity.abs() > 0.08
        ? throwVelocity.sign
        : dragDelta == 0
            ? 0.0
            : dragDelta.sign;
    final direction = rawDirection != 0
        ? rawDirection
        : throwDistance > widget.width * 0.025
            ? _orbitGlowDirection.sign
            : 0.0;
    final distanceFactor =
        (throwDistance / widget.width).clamp(0.0, 2.4).toDouble();
    final velocityFactor =
        (throwVelocity.abs() / 18.0).clamp(0.0, 1.0).toDouble();
    var target = (_rotation / step).roundToDouble() * step;
    var duration = const Duration(milliseconds: 280);

    if (moved && direction != 0) {
      final flingTurns =
          (1.2 + distanceFactor * 3.2 + velocityFactor * 2.4)
              .clamp(1.2, 9.0)
              .toDouble();
      final projected = _rotation + direction * flingTurns * math.pi * 2;
      target = (projected / step).roundToDouble() * step;
      if ((target - _rotation).sign != direction) {
        target += direction * step;
      }
      duration = _vaultRotateSinglePlayDuration;
      _orbitGlowDirection = direction;
      _settleGlowBaseIntensity =
          (0.58 + distanceFactor * 0.18 + velocityFactor * 0.22)
              .clamp(0.58, 1.0)
              .toDouble();
      _orbitGlowIntensity = _settleGlowBaseIntensity;
    } else {
      final travelSteps = ((target - _rotation).abs() / step).clamp(0.2, 1.0);
      duration = Duration(milliseconds: (180 + travelSteps * 120).round());
    }

    _settleController.duration = duration;
    if ((target - _rotation).abs() > 0.002) {
      _startGearSound();
    }
    _settleAnimation = Tween<double>(begin: _rotation, end: target).animate(
      CurvedAnimation(
        parent: _settleController,
        curve: moved ? const _FlingKeepMovingCurve() : Curves.easeOutQuart,
      ),
    );
    _settleController.forward(from: 0);
  }

  void _notifyOrbitInteraction({required bool active}) {
    DeviceOrbitInteractionNotification(active).dispatch(context);
  }

  void _startGearSound() {
    if (_gearSoundActive) return;
    _gearSoundActive = true;
    unawaited(_playGearSound());
  }

  void _stopGearSound() {
    if (!_gearSoundActive) return;
    _gearSoundActive = false;
    unawaited(_stopGearSoundSafely());
  }

  Future<void> _playGearSound() async {
    try {
      await _gearPlayer.play(
        AssetSource('audio/vault_rotate.wav'),
        volume: 0.42,
      );
    } catch (_) {
      _gearSoundActive = false;
    }
  }

  Future<void> _stopGearSoundSafely() async {
    try {
      await _gearPlayer.stop();
    } catch (_) {
      // Audio feedback is non-critical; rotation must remain responsive.
    }
  }

  double _angleFromStagePosition(Offset stagePosition, Offset core) {
    final vector = stagePosition - core;
    return math.atan2(vector.dy, vector.dx);
  }

  double _normalizeAngle(double angle) {
    while (angle > math.pi) {
      angle -= math.pi * 2;
    }
    while (angle < -math.pi) {
      angle += math.pi * 2;
    }
    return angle;
  }

  List<_DeviceAction> _buildActions() {
    return [
      _DeviceAction(
        title: '功率计',
        icon: Icons.bolt,
        onTap: () => Get.to(() => const PowerMeterPage()),
      ),
      _DeviceAction(
        title: '码表',
        icon: Icons.directions_bike,
        onTap: () => Get.to(
          () => const SpeedometerPage(),
          transition: Transition.cupertino,
          duration: const Duration(milliseconds: 300),
        ),
      ),
      _DeviceAction(
        title: '遥控',
        icon: Icons.settings_remote,
        onTap: () => Get.to(() => const RemoteControlPage()),
      ),
      _DeviceAction(
        title: '即将推出',
        icon: Icons.hourglass_bottom,
        onTap: () => Get.snackbar(
          '提示',
          '功能开发中，敬请期待',
          snackPosition: SnackPosition.TOP,
          backgroundColor: TraceColors.deep,
          colorText: TraceColors.text,
          icon: const Icon(Icons.construction, color: TraceColors.amber),
        ),
      ),
    ];
  }
}

class _DeviceAction {
  const _DeviceAction({
    required this.title,
    required this.icon,
    required this.onTap,
  });

  final String title;
  final IconData icon;
  final VoidCallback onTap;
}

class _DeviceLabelGeometry {
  const _DeviceLabelGeometry({
    required this.left,
    required this.top,
    required this.width,
    required this.alignment,
  });

  final double left;
  final double top;
  final double width;
  final TextAlign alignment;
}

class _DeviceNodeLabel extends StatelessWidget {
  const _DeviceNodeLabel({
    required this.title,
    required this.alignment,
    required this.onTap,
  });

  final String title;
  final TextAlign alignment;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: onTap,
      child: Column(
        crossAxisAlignment: alignment == TextAlign.left
            ? CrossAxisAlignment.start
            : alignment == TextAlign.right
                ? CrossAxisAlignment.end
                : CrossAxisAlignment.center,
        children: [
          FittedBox(
            fit: BoxFit.scaleDown,
            alignment: alignment == TextAlign.left
                ? Alignment.centerLeft
                : alignment == TextAlign.right
                    ? Alignment.centerRight
                    : Alignment.center,
            child: Text(
              title,
              textAlign: alignment,
              maxLines: 1,
              style: const TextStyle(
                color: TraceColors.text,
                fontSize: 18,
                fontWeight: FontWeight.w900,
                shadows: [
                  Shadow(color: Color(0x9924F6DE), blurRadius: 14),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _FlingKeepMovingCurve extends Curve {
  const _FlingKeepMovingCurve();

  @override
  double transformInternal(double t) {
    const minimumMotionShare = 0.18;
    final eased = 1 - math.pow(1 - t, 3).toDouble();
    return eased * (1 - minimumMotionShare) + t * minimumMotionShare;
  }
}

/// 舞台几何：核心、四个对角卫星和外侧标签共用的一套坐标
class _DeviceStageGeometry {
  _DeviceStageGeometry(this.width, {required this.rotation})
      : height = width * 1.34,
        coreSize = width * 0.48,
        nodeSize = width * 0.19,
        orbitRadius = width * 0.445,
        core = Offset(width / 2, width * 1.34 * 0.51) {
    final angles = [
      -math.pi * 3 / 4 + rotation, // 左上
      -math.pi / 4 + rotation, // 右上
      math.pi * 3 / 4 + rotation, // 左下
      math.pi / 4 + rotation, // 右下
    ];
    satellites = angles
        .map(
          (angle) =>
              core + Offset(math.cos(angle), math.sin(angle)) * orbitRadius,
        )
        .toList(growable: false);

    final gutter = width * 0.02;
    final sideWidth = width * 0.31;
    final rightLabelLeft = width - sideWidth - gutter;
    labels = List.generate(satellites.length, (index) {
      final satellite = satellites[index];
      final isLeft = satellite.dx < core.dx;
      final isTop = satellite.dy < core.dy;
      final requestedOffset = index < 2 ? 9.0 : -9.0;
      return _DeviceLabelGeometry(
        left: isLeft ? gutter : rightLabelLeft,
        top: satellite.dy + nodeSize * (isTop ? 0.44 : 0.74) + requestedOffset,
        width: sideWidth,
        alignment: isLeft ? TextAlign.left : TextAlign.right,
      );
    }, growable: false);
  }

  final double width;
  final double height;
  final double coreSize;
  final double nodeSize;
  final double orbitRadius;
  final double rotation;
  final Offset core;
  late final List<Offset> satellites;
  late final List<_DeviceLabelGeometry> labels;
}

class _DeviceStagePainter extends CustomPainter {
  const _DeviceStagePainter(
    this.geometry, {
    required this.orbitGlowDirection,
    required this.orbitGlowIntensity,
  });

  final _DeviceStageGeometry geometry;
  final double orbitGlowDirection;
  final double orbitGlowIntensity;

  @override
  void paint(Canvas canvas, Size size) {
    final center = geometry.core;

    // 核心外围大光晕
    final glowPaint = Paint()
      ..shader = RadialGradient(
        colors: [
          TraceColors.cyan.withOpacity(0.2),
          TraceColors.ocean.withOpacity(0.08),
          Colors.transparent,
        ],
      ).createShader(
        Rect.fromCircle(center: center, radius: geometry.orbitRadius * 1.3),
      );
    canvas.drawCircle(center, geometry.orbitRadius * 1.3, glowPaint);

    // 穿过卫星圆心的机械轨道圆
    final orbitPaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.1
      ..color = TraceColors.cyan.withOpacity(0.16);
    canvas.drawCircle(center, geometry.orbitRadius, orbitPaint);
    canvas.drawCircle(
      center,
      geometry.orbitRadius * 1.14,
      orbitPaint..color = TraceColors.cyan.withOpacity(0.09),
    );
    canvas.drawCircle(
      center,
      geometry.orbitRadius * 0.78,
      orbitPaint..color = TraceColors.cyan.withOpacity(0.1),
    );
    canvas.drawCircle(
      center,
      geometry.orbitRadius * 0.64,
      orbitPaint..color = TraceColors.cyan.withOpacity(0.08),
    );
    _paintMotionGlow(canvas, center);

    final tickPaint = Paint()
      ..strokeCap = StrokeCap.round
      ..color = TraceColors.cyan.withOpacity(0.36);
    for (var i = 0; i < 112; i++) {
      final angle = -math.pi / 2 + i * math.pi * 2 / 112;
      final major = i % 14 == 0;
      tickPaint.strokeWidth = major ? 1.2 : 0.75;
      final outer = geometry.orbitRadius * 0.93;
      final inner = geometry.orbitRadius * (major ? 0.8 : 0.86);
      canvas.drawLine(
        center + Offset(math.cos(angle), math.sin(angle)) * inner,
        center + Offset(math.cos(angle), math.sin(angle)) * outer,
        tickPaint,
      );
    }

    // 核心 → 卫星 机械连接臂
    for (final satellite in geometry.satellites) {
      final direction = (satellite - center) / (satellite - center).distance;
      final perpendicular = Offset(-direction.dy, direction.dx);
      final start = center + direction * (geometry.coreSize * 0.5);
      final end = satellite - direction * (geometry.nodeSize * 0.58);

      final armBodyPaint = Paint()
        ..strokeCap = StrokeCap.round
        ..strokeWidth = geometry.width * 0.032
        ..color = TraceColors.ocean.withOpacity(0.54);
      canvas.drawLine(start, end, armBodyPaint);

      final armEdgePaint = Paint()
        ..strokeCap = StrokeCap.round
        ..strokeWidth = 1.4
        ..color = TraceColors.cyan.withOpacity(0.34);
      canvas.drawLine(
        start + perpendicular * geometry.width * 0.014,
        end + perpendicular * geometry.width * 0.014,
        armEdgePaint,
      );
      canvas.drawLine(
        start - perpendicular * geometry.width * 0.014,
        end - perpendicular * geometry.width * 0.014,
        armEdgePaint..color = TraceColors.cyan.withOpacity(0.22),
      );

      final linkPaint = Paint()
        ..strokeWidth = 1.5
        ..shader = LinearGradient(
          colors: [
            TraceColors.cyan.withOpacity(0.68),
            TraceColors.cyan.withOpacity(0.16),
          ],
        ).createShader(Rect.fromPoints(start, end));
      canvas.drawLine(start, end, linkPaint);

      for (final anchor in [0.16, 0.84]) {
        final joint = Offset.lerp(start, end, anchor)!;
        canvas.drawLine(
          joint - perpendicular * geometry.width * 0.028,
          joint + perpendicular * geometry.width * 0.028,
          Paint()
            ..strokeCap = StrokeCap.round
            ..strokeWidth = 2
            ..color = TraceColors.cyanSoft.withOpacity(0.42),
        );
        canvas.drawCircle(
          joint,
          geometry.width * 0.012,
          Paint()
            ..style = PaintingStyle.stroke
            ..strokeWidth = 1.2
            ..color = TraceColors.cyan.withOpacity(0.6),
        );
      }

      final midpoint = Offset.lerp(start, end, 0.5)!;
      canvas.drawCircle(
        midpoint,
        2.2,
        Paint()..color = TraceColors.cyanSoft.withOpacity(0.55),
      );
    }

    final cardinalPaint = Paint()..color = TraceColors.cyanSoft.withOpacity(0.9);
    for (final angle in const [
      -math.pi / 2,
      0.0,
      math.pi / 2,
      math.pi,
    ]) {
      final point = center + Offset(math.cos(angle), math.sin(angle)) * geometry.orbitRadius;
      canvas.drawCircle(point, 3.2, cardinalPaint);
    }

    // 固定种子散布光点
    final random = math.Random(28);
    final dotPaint = Paint();
    for (int i = 0; i < 26; i++) {
      final angle = random.nextDouble() * math.pi * 2;
      final radius = geometry.orbitRadius * (0.5 + random.nextDouble() * 0.75);
      final position = center + Offset(math.cos(angle), math.sin(angle)) * radius;
      dotPaint.color = TraceColors.cyanSoft
          .withOpacity(0.08 + random.nextDouble() * 0.3);
      canvas.drawCircle(position, 0.7 + random.nextDouble() * 1.3, dotPaint);
    }

    // 舞台底部地面反射光
    final floorPaint = Paint()
      ..shader = RadialGradient(
        colors: [
          TraceColors.cyan.withOpacity(0.1),
          Colors.transparent,
        ],
      ).createShader(
        Rect.fromCenter(
          center: Offset(size.width / 2, size.height * 0.99),
          width: size.width * 1.1,
          height: size.height * 0.24,
        ),
      );
    canvas.drawOval(
      Rect.fromCenter(
        center: Offset(size.width / 2, size.height * 0.99),
        width: size.width * 1.1,
        height: size.height * 0.24,
      ),
      floorPaint,
    );
  }

  void _paintMotionGlow(Canvas canvas, Offset center) {
    if (orbitGlowIntensity <= 0.01 || orbitGlowDirection == 0) return;

    final direction = orbitGlowDirection.sign;
    final headAngle = -math.pi / 2 + geometry.rotation;
    final tailSpan = math.pi * 1.28;

    _paintMotionRingTrail(
      canvas,
      center,
      geometry.orbitRadius * 1.14,
      headAngle,
      direction,
      tailSpan,
      glowStrokeWidth: 18,
      rimStrokeWidth: 2.8,
      opacityScale: 0.92,
    );
    _paintMotionRingTrail(
      canvas,
      center,
      geometry.orbitRadius * 0.78,
      headAngle,
      direction,
      tailSpan,
      glowStrokeWidth: 14,
      rimStrokeWidth: 2.2,
      opacityScale: 0.78,
    );
    _paintMotionRingTrail(
      canvas,
      center,
      geometry.orbitRadius * 0.64,
      headAngle,
      direction,
      tailSpan,
      glowStrokeWidth: 11,
      rimStrokeWidth: 1.8,
      opacityScale: 0.68,
    );
    _paintMotionTickTrail(canvas, center, headAngle, direction, tailSpan);

    final radius = geometry.orbitRadius;
    final head =
        center + Offset(math.cos(headAngle), math.sin(headAngle)) * radius;
    final headPaint = Paint()
      ..shader = RadialGradient(
        colors: [
          TraceColors.cyanSoft.withOpacity(0.5 * orbitGlowIntensity),
          TraceColors.cyan.withOpacity(0.22 * orbitGlowIntensity),
          Colors.transparent,
        ],
      ).createShader(
        Rect.fromCircle(center: head, radius: geometry.nodeSize * 0.78),
      );
    canvas.drawCircle(head, geometry.nodeSize * 0.78, headPaint);
  }

  void _paintMotionRingTrail(
    Canvas canvas,
    Offset center,
    double radius,
    double headAngle,
    double direction,
    double tailSpan, {
    required double glowStrokeWidth,
    required double rimStrokeWidth,
    required double opacityScale,
  }) {
    final rect = Rect.fromCircle(center: center, radius: radius);
    final trailStart = headAngle - direction * tailSpan;
    final trailSweep = direction * tailSpan;
    final hotStart = headAngle - direction * tailSpan * 0.58;
    final hotSweep = direction * tailSpan * 0.58;

    final glowPaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..strokeWidth = glowStrokeWidth
      ..color = TraceColors.cyanSoft
          .withOpacity(0.12 * orbitGlowIntensity * opacityScale)
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 8);
    canvas.drawArc(rect, trailStart, trailSweep, false, glowPaint);

    final rimPaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..strokeWidth = rimStrokeWidth
      ..color = TraceColors.text
          .withOpacity(0.36 * orbitGlowIntensity * opacityScale);
    canvas.drawArc(rect, hotStart, hotSweep, false, rimPaint);

    final leadingPaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..strokeWidth = rimStrokeWidth + 0.9
      ..color = TraceColors.cyanSoft
          .withOpacity(0.5 * orbitGlowIntensity * opacityScale);
    canvas.drawArc(
      rect,
      headAngle - direction * math.pi * 0.08,
      direction * math.pi * 0.08,
      false,
      leadingPaint,
    );
  }

  void _paintMotionTickTrail(
    Canvas canvas,
    Offset center,
    double headAngle,
    double direction,
    double tailSpan,
  ) {
    const tickCount = 112;
    final activeTickCount = (tickCount * tailSpan / (math.pi * 2)).ceil();
    final tickGlowPaint = Paint()..strokeCap = StrokeCap.round;
    final tickHotPaint = Paint()..strokeCap = StrokeCap.round;

    for (var i = 0; i <= activeTickCount; i++) {
      final progress = 1 - i / activeTickCount;
      if (progress <= 0) continue;

      final rawAngle = headAngle - direction * i * math.pi * 2 / tickCount;
      final tickIndex =
          ((rawAngle + math.pi / 2) / (math.pi * 2) * tickCount).round();
      final angle = -math.pi / 2 + tickIndex * math.pi * 2 / tickCount;
      final major = tickIndex % 14 == 0;
      final opacity = orbitGlowIntensity * math.pow(progress, 0.72).toDouble();
      final outer = geometry.orbitRadius * 0.94;
      final inner = geometry.orbitRadius * (major ? 0.78 : 0.84);
      final start = center + Offset(math.cos(angle), math.sin(angle)) * inner;
      final end = center + Offset(math.cos(angle), math.sin(angle)) * outer;

      tickGlowPaint
        ..strokeWidth = major ? 2.9 : 2.2
        ..color = TraceColors.cyanSoft.withOpacity(0.16 * opacity);
      canvas.drawLine(start, end, tickGlowPaint);

      tickHotPaint
        ..strokeWidth = major ? 1.5 : 1.0
        ..color = TraceColors.text.withOpacity(0.44 * opacity);
      canvas.drawLine(start, end, tickHotPaint);
    }
  }
  @override
  bool shouldRepaint(covariant _DeviceStagePainter oldDelegate) {
    return oldDelegate.geometry.width != geometry.width ||
        oldDelegate.geometry.rotation != geometry.rotation ||
        oldDelegate.orbitGlowDirection != orbitGlowDirection ||
        oldDelegate.orbitGlowIntensity != orbitGlowIntensity;
  }
}

/// 中央“设备中心”核心：强发光青环 + 深色盘面 + 蓝牙圆钮
class _DeviceCore extends StatelessWidget {
  const _DeviceCore({required this.size});

  final double size;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        border: Border.all(color: TraceColors.cyan, width: 3),
        boxShadow: [
          BoxShadow(
            color: TraceColors.cyan.withOpacity(0.55),
            blurRadius: 34,
            spreadRadius: 1,
          ),
          BoxShadow(
            color: TraceColors.cyan.withOpacity(0.22),
            blurRadius: 80,
            spreadRadius: 14,
          ),
        ],
      ),
      child: Container(
        decoration: const BoxDecoration(
          shape: BoxShape.circle,
          gradient: RadialGradient(
            colors: [
              Color(0xFF0D3844),
              Color(0xFF072028),
              Color(0xFF03141B),
            ],
            stops: [0, 0.6, 1],
          ),
        ),
        child: Stack(
          alignment: Alignment.center,
          children: [
            // 盘面同心装饰环
            CustomPaint(
              size: Size.square(size),
              painter: _DeviceCoreDialPainter(),
            ),
            Container(
              margin: EdgeInsets.all(size * 0.075),
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                border: Border.all(
                  color: TraceColors.cyan.withOpacity(0.3),
                  width: 1,
                ),
              ),
            ),
            Container(
              margin: EdgeInsets.all(size * 0.14),
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                border: Border.all(
                  color: TraceColors.cyan.withOpacity(0.14),
                  width: 1,
                ),
              ),
            ),
            Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(
                  '设备中心',
                  style: TextStyle(
                    color: TraceColors.text,
                    fontSize: size * 0.15,
                    fontWeight: FontWeight.w900,
                    letterSpacing: 2,
                    shadows: const [
                      Shadow(color: Color(0x9924F6DE), blurRadius: 16),
                    ],
                  ),
                ),
                SizedBox(height: size * 0.075),
                Container(
                  width: size * 0.2,
                  height: size * 0.2,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: const Color(0xFF041A22),
                    border: Border.all(
                      color: TraceColors.cyan.withOpacity(0.65),
                      width: 1.2,
                    ),
                    boxShadow: [
                      BoxShadow(
                        color: TraceColors.cyan.withOpacity(0.4),
                        blurRadius: 14,
                        spreadRadius: -2,
                      ),
                    ],
                  ),
                  child: Icon(
                    Icons.bluetooth,
                    color: TraceColors.cyan,
                    size: size * 0.11,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _DeviceCoreDialPainter extends CustomPainter {
  const _DeviceCoreDialPainter();

  @override
  void paint(Canvas canvas, Size size) {
    final center = size.center(Offset.zero);
    final radius = size.shortestSide / 2;
    final tickPaint = Paint()
      ..strokeCap = StrokeCap.round
      ..color = TraceColors.cyanSoft.withOpacity(0.22);

    for (var i = 0; i < 96; i++) {
      final angle = -math.pi / 2 + i * math.pi * 2 / 96;
      final major = i % 12 == 0;
      tickPaint.strokeWidth = major ? 1.2 : 0.65;
      final outer = radius * 0.96;
      final inner = radius * (major ? 0.83 : 0.88);
      canvas.drawLine(
        center + Offset(math.cos(angle), math.sin(angle)) * inner,
        center + Offset(math.cos(angle), math.sin(angle)) * outer,
        tickPaint,
      );
    }

    final sweepPaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = radius * 0.08
      ..strokeCap = StrokeCap.round
      ..shader = SweepGradient(
        colors: [
          Colors.transparent,
          TraceColors.cyan.withOpacity(0.18),
          TraceColors.cyanSoft.withOpacity(0.45),
          Colors.transparent,
        ],
        stops: const [0, 0.18, 0.32, 0.55],
      ).createShader(Rect.fromCircle(center: center, radius: radius * 0.74));
    canvas.drawArc(
      Rect.fromCircle(center: center, radius: radius * 0.72),
      -math.pi * 0.98,
      math.pi * 1.42,
      false,
      sweepPaint,
    );
  }

  @override
  bool shouldRepaint(covariant _DeviceCoreDialPainter oldDelegate) => false;
}
