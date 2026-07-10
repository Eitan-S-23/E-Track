import 'dart:math' as math;

import 'package:flutter/material.dart';

class TraceColors {
  static const ink = Color(0xFF02070C);
  static const deep = Color(0xFF061821);
  static const ocean = Color(0xFF0B3540);
  static const cyan = Color(0xFF24F6DE);
  static const cyanSoft = Color(0xFF8DFFF0);
  static const mint = Color(0xFF5EF1C7);
  static const amber = Color(0xFFFFCF66);
  static const rose = Color(0xFFFF5E8E);
  static const text = Color(0xFFEAFDF7);
  static const muted = Color(0xFF8FB8B6);
}

class TraceTheme {
  static const double bottomNavHeight = 104;
  static const double pageBottomPadding = 138;

  static const pageGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [
      TraceColors.ink,
      Color(0xFF04111A),
      TraceColors.deep,
      Color(0xFF010409),
    ],
  );
}

class TracePageScaffold extends StatelessWidget {
  const TracePageScaffold({
    super.key,
    required this.child,
    this.paintBackground = true,
  });

  final Widget child;
  final bool paintBackground;

  @override
  Widget build(BuildContext context) {
    if (!paintBackground) {
      return child;
    }

    return Container(
      decoration: const BoxDecoration(gradient: TraceTheme.pageGradient),
      child: Stack(
        children: [
          const Positioned.fill(
            child: TraceAnimatedAtmosphere(),
          ),
          child,
        ],
      ),
    );
  }
}

class TraceAnimatedAtmosphere extends StatefulWidget {
  const TraceAnimatedAtmosphere({super.key});

  @override
  State<TraceAnimatedAtmosphere> createState() => _TraceAnimatedAtmosphereState();
}

class _TraceAnimatedAtmosphereState extends State<TraceAnimatedAtmosphere>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 14),
    )..repeat();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return IgnorePointer(
      child: AnimatedBuilder(
        animation: _controller,
        builder: (context, child) {
          return CustomPaint(
            painter: TraceAtmospherePainter(phase: _controller.value),
          );
        },
      ),
    );
  }
}

class TraceAtmospherePainter extends CustomPainter {
  const TraceAtmospherePainter({this.phase = 0});

  final double phase;

  @override
  void paint(Canvas canvas, Size size) {
    final washPaint = Paint()
      ..shader = const LinearGradient(
        begin: Alignment.topCenter,
        end: Alignment.bottomCenter,
        colors: [
          Color(0x2207A99F),
          Colors.transparent,
          Color(0x66000105),
        ],
        stops: [0, 0.52, 1],
      ).createShader(Offset.zero & size);
    canvas.drawRect(Offset.zero & size, washPaint);

    final gridPaint = Paint()
      ..color = TraceColors.cyan.withOpacity(0.022)
      ..strokeWidth = 1;

    const step = 36.0;
    for (double x = -size.height; x < size.width; x += step) {
      canvas.drawLine(
        Offset(x, 0),
        Offset(x + size.height, size.height),
        gridPaint,
      );
    }

    final glowPaint = Paint()
      ..shader = RadialGradient(
        colors: [
          TraceColors.cyan.withOpacity(0.16),
          TraceColors.ocean.withOpacity(0.05),
          Colors.transparent,
        ],
      ).createShader(
        Rect.fromCircle(
          center: Offset(size.width * 0.28, size.height * 0.24),
          radius: size.width * 0.85,
        ),
      );
    canvas.drawCircle(
      Offset(size.width * 0.28, size.height * 0.24),
      size.width * 0.85,
      glowPaint,
    );

    final cornerGlowPaint = Paint()
      ..shader = RadialGradient(
        colors: [TraceColors.cyanSoft.withOpacity(0.08), Colors.transparent],
      ).createShader(
        Rect.fromCircle(
          center: Offset(size.width * 0.94, size.height * 0.12),
          radius: size.width * 0.5,
        ),
      );
    canvas.drawCircle(
      Offset(size.width * 0.94, size.height * 0.12),
      size.width * 0.5,
      cornerGlowPaint,
    );

    // 固定种子星点，保证每帧稳定不闪烁
    final random = math.Random(7);
    final starPaint = Paint();
    for (int i = 0; i < 90; i++) {
      final dx = random.nextDouble() * size.width;
      final dy = random.nextDouble() * size.height;
      final radius = 0.4 + random.nextDouble() * 1.1;
      final opacity = 0.05 + random.nextDouble() * 0.3;
      starPaint.color = (random.nextBool()
              ? TraceColors.cyanSoft
              : Colors.white)
          .withOpacity(opacity);
      canvas.drawCircle(Offset(dx, dy), radius, starPaint);
    }

    // 远景大圆弧装饰
    final arcPaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1
      ..color = TraceColors.cyan.withOpacity(0.07);
    canvas.drawCircle(
      Offset(size.width * -0.18, size.height * 0.34),
      size.width * 0.52,
      arcPaint,
    );
    canvas.drawCircle(
      Offset(size.width * 1.12, size.height * 0.78),
      size.width * 0.58,
      arcPaint,
    );

    final topLinePaint = Paint()
      ..shader = LinearGradient(
        colors: [
          Colors.transparent,
          TraceColors.cyan.withOpacity(0.18),
          Colors.transparent,
        ],
      ).createShader(
        Rect.fromLTWH(0, size.height * 0.12, size.width, 1),
      );
    canvas.drawLine(
      Offset(size.width * 0.08, size.height * 0.12),
      Offset(size.width * 0.92, size.height * 0.12),
      topLinePaint,
    );

    final sweepCenter = Offset(size.width * 0.5, size.height * 0.44);
    final sweepRadius = size.shortestSide * 0.72;
    final sweepAngle = phase * math.pi * 2 - math.pi / 2;
    final sweepPaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2
      ..strokeCap = StrokeCap.round
      ..shader = SweepGradient(
        startAngle: sweepAngle - math.pi * 0.22,
        endAngle: sweepAngle + math.pi * 0.22,
        colors: [
          Colors.transparent,
          TraceColors.cyan.withOpacity(0.02),
          TraceColors.cyanSoft.withOpacity(0.18),
          Colors.transparent,
        ],
        stops: const [0, 0.45, 0.75, 1],
        transform: GradientRotation(sweepAngle),
      ).createShader(Rect.fromCircle(center: sweepCenter, radius: sweepRadius));
    canvas.drawArc(
      Rect.fromCircle(center: sweepCenter, radius: sweepRadius),
      sweepAngle - math.pi * 0.2,
      math.pi * 0.42,
      false,
      sweepPaint,
    );

    final scanPaint = Paint()
      ..strokeWidth = 1
      ..shader = LinearGradient(
        colors: [
          Colors.transparent,
          TraceColors.cyanSoft.withOpacity(0.13),
          Colors.transparent,
        ],
      ).createShader(Rect.fromLTWH(0, 0, size.width, 1));
    for (var i = 0; i < 4; i++) {
      final y = ((phase + i * 0.25) % 1.0) * size.height;
      canvas.drawLine(
        Offset(size.width * 0.06, y),
        Offset(size.width * 0.94, y),
        scanPaint,
      );
    }

    final particlePaint = Paint()..strokeCap = StrokeCap.round;
    final linePaint = Paint()
      ..strokeWidth = 0.7
      ..color = TraceColors.cyan.withOpacity(0.08);
    final particles = <Offset>[];
    for (var i = 0; i < 18; i++) {
      final seed = i * 37.0;
      final x = ((math.sin(seed + phase * math.pi * 2) * 0.5 + 0.5) *
              size.width *
              0.86) +
          size.width * 0.07;
      final y = ((math.cos(seed * 0.7 + phase * math.pi * 1.4) * 0.5 + 0.5) *
              size.height *
              0.72) +
          size.height * 0.12;
      particles.add(Offset(x, y));
    }
    for (var i = 0; i < particles.length - 1; i++) {
      if (i % 3 == 0) {
        canvas.drawLine(particles[i], particles[i + 1], linePaint);
      }
    }
    for (var i = 0; i < particles.length; i++) {
      final pulse = 0.55 + math.sin(phase * math.pi * 2 + i) * 0.25;
      particlePaint.color = TraceColors.cyanSoft.withOpacity(0.18 + pulse * 0.16);
      canvas.drawCircle(particles[i], 1.1 + pulse * 1.4, particlePaint);
    }
  }

  @override
  bool shouldRepaint(covariant TraceAtmospherePainter oldDelegate) {
    return oldDelegate.phase != phase;
  }
}

/// 分区标题：左侧发光竖条 + 标题文字（对应设计图“功能指南 / 更多内容”样式）
class TraceSectionHeader extends StatelessWidget {
  const TraceSectionHeader({
    super.key,
    required this.title,
    this.color = TraceColors.cyan,
  });

  final String title;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 3.5,
          height: 15,
          decoration: BoxDecoration(
            color: color,
            borderRadius: BorderRadius.circular(2),
            boxShadow: [
              BoxShadow(color: color.withOpacity(0.7), blurRadius: 8),
            ],
          ),
        ),
        const SizedBox(width: 9),
        Text(
          title,
          style: const TextStyle(
            color: TraceColors.text,
            fontSize: 16,
            fontWeight: FontWeight.w800,
            letterSpacing: 0.4,
          ),
        ),
      ],
    );
  }
}

/// 发光圆形功能节点：深色圆盘 + 霓虹描边 + 圆外下方标签
/// 设备页对角卫星与“我的”页功能网格共用
class TraceGlowNode extends StatelessWidget {
  const TraceGlowNode({
    super.key,
    required this.size,
    required this.icon,
    required this.onTap,
    this.label,
    this.sublabel,
    this.color = TraceColors.cyan,
    this.labelWidth,
    this.semanticLabel,
  });

  final double size;
  final IconData icon;
  final VoidCallback onTap;
  final String? label;
  final String? sublabel;
  final Color color;
  final double? labelWidth;
  final String? semanticLabel;

  @override
  Widget build(BuildContext context) {
    final textWidth = labelWidth ?? size * 1.5;

    return Semantics(
      button: true,
      label: semanticLabel ?? [label, sublabel].whereType<String>().join(' '),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          SizedBox(
            width: size * 1.36,
            height: size * 1.36,
            child: Stack(
              alignment: Alignment.center,
              children: [
                Positioned.fill(
                  child: CustomPaint(
                    painter: _TraceNodeRingsPainter(color: color),
                  ),
                ),
                Material(
                  color: Colors.transparent,
                  shape: const CircleBorder(),
                  child: InkWell(
                    customBorder: const CircleBorder(),
                    onTap: onTap,
                    child: Ink(
                      width: size,
                      height: size,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        gradient: RadialGradient(
                          colors: [
                            color.withOpacity(0.2),
                            const Color(0xFF092934).withOpacity(0.97),
                            const Color(0xFF030E15).withOpacity(0.99),
                          ],
                          stops: const [0, 0.58, 1],
                        ),
                        border: Border.all(
                          color: color.withOpacity(0.74),
                          width: 1.3,
                        ),
                      ),
                      child: Container(
                        margin: EdgeInsets.all(size * 0.08),
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          border: Border.all(color: color.withOpacity(0.26)),
                        ),
                        child: Icon(
                          icon,
                          color: TraceColors.cyanSoft,
                          size: size * 0.38,
                          shadows: [
                            Shadow(
                              color: color.withOpacity(0.92),
                              blurRadius: 16,
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
          if (label != null) ...[
            SizedBox(height: size * 0.03),
            SizedBox(
              width: textWidth,
              child: FittedBox(
                fit: BoxFit.scaleDown,
                child: Text(
                  label!,
                  textAlign: TextAlign.center,
                  maxLines: 1,
                  style: const TextStyle(
                    color: TraceColors.text,
                    fontSize: 15.5,
                    fontWeight: FontWeight.w900,
                  ),
                ),
              ),
            ),
          ],
          if (sublabel != null) ...[
            const SizedBox(height: 3),
            SizedBox(
              width: textWidth,
              child: Text(
                sublabel!,
                textAlign: TextAlign.center,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  color: TraceColors.muted.withOpacity(0.9),
                  fontSize: 10.5,
                  fontWeight: FontWeight.w600,
                  letterSpacing: 0.2,
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _TraceNodeRingsPainter extends CustomPainter {
  const _TraceNodeRingsPainter({required this.color});

  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    final center = size.center(Offset.zero);
    final radius = size.shortestSide / 2;
    final glowPaint = Paint()
      ..shader = RadialGradient(
        colors: [
          color.withOpacity(0.18),
          color.withOpacity(0.06),
          Colors.transparent,
        ],
      ).createShader(Rect.fromCircle(center: center, radius: radius * 0.72));
    canvas.drawCircle(center, radius * 0.72, glowPaint);

    final ringPaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1
      ..color = color.withOpacity(0.24);

    canvas.drawCircle(center, radius * 0.47, ringPaint);
    canvas.drawCircle(
      center,
      radius * 0.67,
      ringPaint..color = color.withOpacity(0.18),
    );
    canvas.drawCircle(
      center,
      radius * 0.9,
      ringPaint..color = color.withOpacity(0.12),
    );

    final tickPaint = Paint()
      ..strokeWidth = 0.8
      ..strokeCap = StrokeCap.round
      ..color = color.withOpacity(0.32);

    for (var i = 0; i < 36; i++) {
      final angle = -math.pi / 2 + i * math.pi * 2 / 36;
      final major = i % 6 == 0;
      final outer = radius * 0.86;
      final inner = radius * (major ? 0.76 : 0.81);
      final start = center + Offset(math.cos(angle), math.sin(angle)) * inner;
      final end = center + Offset(math.cos(angle), math.sin(angle)) * outer;
      canvas.drawLine(start, end, tickPaint);
    }

    final dotPaint = Paint()..color = color.withOpacity(0.75);
    for (final angle in const [0.0, math.pi / 2, math.pi, math.pi * 1.5]) {
      final position = center + Offset(math.cos(angle), math.sin(angle)) * radius * 0.88;
      canvas.drawCircle(position, 2, dotPaint);
    }
  }

  @override
  bool shouldRepaint(covariant _TraceNodeRingsPainter oldDelegate) {
    return oldDelegate.color != color;
  }
}

class TraceDialogAction {
  const TraceDialogAction({
    required this.label,
    required this.onPressed,
    this.isPrimary = false,
    this.color = TraceColors.cyan,
  });

  final String label;
  final ValueChanged<BuildContext> onPressed;
  final bool isPrimary;
  final Color color;
}

class TraceDialog extends StatelessWidget {
  const TraceDialog({
    super.key,
    required this.title,
    this.message,
    this.content,
    this.icon,
    this.color = TraceColors.cyan,
    this.actions = const [],
  }) : assert(message != null || content != null);

  final String title;
  final String? message;
  final Widget? content;
  final IconData? icon;
  final Color color;
  final List<TraceDialogAction> actions;

  static void close(BuildContext context) {
    final navigator = Navigator.of(context, rootNavigator: true);
    if (navigator.canPop()) {
      navigator.pop();
    }
  }

  @override
  Widget build(BuildContext context) {
    final body = content ?? Text(message!);

    return Dialog(
      elevation: 0,
      insetPadding: const EdgeInsets.symmetric(horizontal: 28, vertical: 24),
      backgroundColor: Colors.transparent,
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 420),
        child: Container(
          padding: const EdgeInsets.fromLTRB(20, 20, 20, 18),
          decoration: BoxDecoration(
            color: const Color(0xFF061821).withOpacity(0.96),
            borderRadius: BorderRadius.circular(30),
            border: Border.all(color: color.withOpacity(0.24)),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withOpacity(0.58),
                blurRadius: 34,
                offset: const Offset(0, 20),
              ),
              BoxShadow(
                color: color.withOpacity(0.2),
                blurRadius: 34,
                spreadRadius: -12,
              ),
            ],
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.center,
                children: [
                  Container(
                    width: 46,
                    height: 46,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: color.withOpacity(0.14),
                      border: Border.all(color: color.withOpacity(0.34)),
                    ),
                    child: Icon(icon ?? Icons.info_outline, color: color, size: 24),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      title,
                      style: const TextStyle(
                        color: TraceColors.text,
                        fontSize: 22,
                        height: 1.15,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              Flexible(
                child: DefaultTextStyle(
                  style: const TextStyle(
                    color: TraceColors.muted,
                    fontSize: 14,
                    height: 1.5,
                    fontWeight: FontWeight.w600,
                  ),
                  child: SingleChildScrollView(child: body),
                ),
              ),
              if (actions.isNotEmpty) ...[
                const SizedBox(height: 20),
                Align(
                  alignment: Alignment.centerRight,
                  child: Wrap(
                    spacing: 10,
                    runSpacing: 10,
                    children: actions
                        .map((action) => _TraceDialogButton(action: action))
                        .toList(growable: false),
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _TraceDialogButton extends StatelessWidget {
  const _TraceDialogButton({required this.action});

  final TraceDialogAction action;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      borderRadius: BorderRadius.circular(999),
      child: InkWell(
        borderRadius: BorderRadius.circular(999),
        onTap: () => action.onPressed(context),
        child: Ink(
          padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 11),
          decoration: BoxDecoration(
            color: action.isPrimary ? action.color.withOpacity(0.88) : Colors.transparent,
            borderRadius: BorderRadius.circular(999),
            border: Border.all(
              color: action.isPrimary
                  ? action.color.withOpacity(0.7)
                  : action.color.withOpacity(0.24),
            ),
            boxShadow: action.isPrimary
                ? [
                    BoxShadow(
                      color: action.color.withOpacity(0.24),
                      blurRadius: 22,
                      spreadRadius: -8,
                    ),
                  ]
                : const [],
          ),
          child: Text(
            action.label,
            style: TextStyle(
              color: action.isPrimary ? TraceColors.ink : action.color,
              fontSize: 14,
              fontWeight: FontWeight.w900,
            ),
          ),
        ),
      ),
    );
  }
}
