import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:get/get.dart';

import '../services/announcement_service.dart';
import 'trace_ui.dart';

class DiscoverTabPage extends StatelessWidget {
  const DiscoverTabPage({super.key});

  @override
  Widget build(BuildContext context) {
    return TracePageScaffold(
      paintBackground: false,
      child: SafeArea(
        bottom: false,
        child: SingleChildScrollView(
          physics: const BouncingScrollPhysics(),
          padding: const EdgeInsets.fromLTRB(
            18,
            18,
            18,
            TraceTheme.pageBottomPadding,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                '发现',
                style: TextStyle(
                  color: TraceColors.text,
                  fontSize: 30,
                  fontWeight: FontWeight.w900,
                  letterSpacing: 2,
                  shadows: [
                    Shadow(color: Color(0x6624F6DE), blurRadius: 18),
                  ],
                ),
              ).animate().fadeIn(duration: 420.ms).slideY(begin: 0.14, end: 0),
              const SizedBox(height: 16),
              const _HeroCarousel()
                  .animate(delay: 60.ms)
                  .fadeIn(duration: 480.ms)
                  .slideY(begin: 0.1, end: 0),
              const SizedBox(height: 24),
              const TraceSectionHeader(title: '功能指南')
                  .animate(delay: 140.ms)
                  .fadeIn(duration: 420.ms),
              const SizedBox(height: 14),
              _buildGuideCards()
                  .animate(delay: 180.ms)
                  .fadeIn(duration: 480.ms)
                  .slideY(begin: 0.08, end: 0),
              const SizedBox(height: 24),
              const TraceSectionHeader(title: '更多内容')
                  .animate(delay: 240.ms)
                  .fadeIn(duration: 420.ms),
              const SizedBox(height: 14),
              _buildMoreRows()
                  .animate(delay: 280.ms)
                  .fadeIn(duration: 480.ms)
                  .slideY(begin: 0.08, end: 0),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildGuideCards() {
    final guides = [
      const _GuideData(
        title: '功率计使用指南',
        icon: Icons.bolt,
        points: ['连接 BLE 设备', '实时功率显示', '校准与设置', '数据记录与查看'],
        steps: [
          '从设备页进入功率计。',
          '扫描并选择 BLE 设备。',
          '进入监控后可保存设备，便于长期查看。',
        ],
      ),
      const _GuideData(
        title: '码表入门',
        icon: Icons.directions_bike,
        points: ['连接码表设备', '速度/距离显示', 'OTA 升级固件'],
        steps: [
          '从设备页进入码表。',
          '连接码表设备后查看实时骑行数据。',
          '需要升级时在码表功能内执行 OTA。',
        ],
      ),
      const _GuideData(
        title: '遥控器使用',
        icon: Icons.settings_remote,
        points: ['连接蓝牙遥控', '按键映射说明', '发送控制指令'],
        steps: [
          '从设备页进入遥控。',
          '连接蓝牙设备后配置控制按钮。',
          '点击按钮发送对应控制指令。',
        ],
      ),
    ];

    return SizedBox(
      height: 200,
      child: ListView.separated(
        physics: const BouncingScrollPhysics(),
        scrollDirection: Axis.horizontal,
        clipBehavior: Clip.none,
        itemCount: guides.length,
        separatorBuilder: (_, __) => const SizedBox(width: 12),
        itemBuilder: (context, index) => _GuideCard(data: guides[index]),
      ),
    );
  }

  Widget _buildMoreRows() {
    final rows = [
      _MoreRowData(
        title: '公告',
        subtitle: '查看后台通知与最新版本发布说明',
        icon: Icons.campaign_outlined,
        onTap: _showAnnouncementsDialog,
      ),
      _MoreRowData(
        title: '常见问题',
        subtitle: '查看常见问题与解决方法',
        icon: Icons.help_outline,
        onTap: () => _showContentDialog(
          '常见问题',
          Icons.help_outline,
          const [
            '扫描不到设备：确认系统蓝牙与定位权限已开启。',
            '连接后无数据：确认设备正在广播对应服务与特征。',
            '连接易断开：缩短距离并远离强干扰源。',
          ],
        ),
      ),
      _MoreRowData(
        title: '使用技巧',
        subtitle: '发现更多实用功能与小技巧',
        icon: Icons.tips_and_updates_outlined,
        onTap: () => _showContentDialog(
          '使用技巧',
          Icons.tips_and_updates_outlined,
          const [
            '功率计监控页可保存设备，下次快速直连。',
            '码表支持 OTA 升级，保持固件最新体验更佳。',
            '遥控按键可自定义指令，适配不同设备协议。',
          ],
        ),
      ),
    ];

    return Column(
      children: [
        for (var i = 0; i < rows.length; i++) ...[
          _MoreRow(data: rows[i]),
          if (i != rows.length - 1) const SizedBox(height: 10),
        ],
      ],
    );
  }

  static void _showGuideDialog(_GuideData data) {
    _showContentDialog(data.title, data.icon, data.steps);
  }

  static void _showAnnouncementsDialog() {
    Get.dialog<void>(
      TraceDialog(
        title: '公告',
        icon: Icons.campaign_outlined,
        color: TraceColors.cyan,
        content: const _AnnouncementsDialogContent(),
        actions: [
          TraceDialogAction(
            label: '确定',
            isPrimary: true,
            onPressed: TraceDialog.close,
          ),
        ],
      ),
      barrierColor: Colors.black.withOpacity(0.62),
    );
  }

  static void _showContentDialog(
    String title,
    IconData icon,
    List<String> lines,
  ) {
    Get.dialog<void>(
      TraceDialog(
        title: title,
        icon: icon,
        color: TraceColors.cyan,
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            for (var i = 0; i < lines.length; i++) ...[
              Text('${i + 1}. ${lines[i]}'),
              if (i != lines.length - 1) const SizedBox(height: 8),
            ],
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
      barrierColor: Colors.black.withOpacity(0.62),
    );
  }
}

class _AnnouncementsDialogContent extends StatefulWidget {
  const _AnnouncementsDialogContent();

  @override
  State<_AnnouncementsDialogContent> createState() =>
      _AnnouncementsDialogContentState();
}

class _AnnouncementsDialogContentState
    extends State<_AnnouncementsDialogContent> {
  late final Future<List<TraceAnnouncement>> _announcementsFuture =
      AnnouncementService.fetchAnnouncements();
  final PageController _controller = PageController();
  int _index = 0;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<List<TraceAnnouncement>>(
      future: _announcementsFuture,
      builder: (context, snapshot) {
        if (!snapshot.hasData) {
          return const SizedBox(
            height: 220,
            child: Center(
              child: CircularProgressIndicator(color: TraceColors.cyan),
            ),
          );
        }

        final announcements = snapshot.data!;
        return Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            SizedBox(
              height: 292,
              child: PageView.builder(
                controller: _controller,
                physics: const BouncingScrollPhysics(),
                itemCount: announcements.length,
                onPageChanged: (index) {
                  setState(() {
                    _index = index;
                  });
                },
                itemBuilder: (context, index) {
                  return _AnnouncementPage(data: announcements[index]);
                },
              ),
            ),
            const SizedBox(height: 12),
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                for (var i = 0; i < announcements.length; i++) ...[
                  if (i != 0) const SizedBox(width: 6),
                  AnimatedContainer(
                    duration: const Duration(milliseconds: 220),
                    width: i == _index ? 18 : 5,
                    height: 5,
                    decoration: BoxDecoration(
                      color: i == _index
                          ? TraceColors.cyan
                          : TraceColors.muted.withOpacity(0.35),
                      borderRadius: BorderRadius.circular(3),
                    ),
                  ),
                ],
              ],
            ),
          ],
        );
      },
    );
  }
}

class _AnnouncementPage extends StatelessWidget {
  const _AnnouncementPage({required this.data});

  final TraceAnnouncement data;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 2),
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 14),
      decoration: BoxDecoration(
        color: const Color(0xFF071B25).withOpacity(0.78),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: TraceColors.cyan.withOpacity(0.2)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
                decoration: BoxDecoration(
                  color: TraceColors.cyan.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(999),
                  border: Border.all(color: TraceColors.cyan.withOpacity(0.3)),
                ),
                child: Text(
                  data.type.label,
                  style: const TextStyle(
                    color: TraceColors.cyan,
                    fontSize: 11,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
              const Spacer(),
              if (data.releaseTag != null)
                Text(
                  data.releaseTag!,
                  style: TextStyle(
                    color: TraceColors.muted.withOpacity(0.85),
                    fontSize: 11,
                    fontWeight: FontWeight.w700,
                  ),
                ),
            ],
          ),
          const SizedBox(height: 13),
          Text(
            data.title,
            style: const TextStyle(
              color: TraceColors.text,
              fontSize: 18,
              height: 1.2,
              fontWeight: FontWeight.w900,
            ),
          ),
          const SizedBox(height: 12),
          Expanded(
            child: SingleChildScrollView(
              physics: const BouncingScrollPhysics(),
              child: _AnnouncementBody(text: data.body),
            ),
          ),
        ],
      ),
    );
  }
}

class _AnnouncementBody extends StatelessWidget {
  const _AnnouncementBody({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    final lines = text
        .split(RegExp(r'\r?\n'))
        .map((line) => line.trim())
        .where((line) => line.isNotEmpty)
        .toList(growable: false);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (var i = 0; i < lines.length; i++) ...[
          _AnnouncementLine(line: lines[i]),
          if (i != lines.length - 1) const SizedBox(height: 8),
        ],
      ],
    );
  }
}

class _AnnouncementLine extends StatelessWidget {
  const _AnnouncementLine({required this.line});

  final String line;

  @override
  Widget build(BuildContext context) {
    final heading = line.replaceFirst(RegExp(r'^#{1,3}\s+'), '');
    if (heading != line) {
      return Text(
        heading,
        style: const TextStyle(
          color: TraceColors.text,
          fontSize: 15,
          fontWeight: FontWeight.w900,
        ),
      );
    }

    final bullet = line.replaceFirst(RegExp(r'^[-*]\s+'), '');
    if (bullet != line) {
      return Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 5,
            height: 5,
            margin: const EdgeInsets.only(top: 8, right: 8),
            decoration: const BoxDecoration(
              color: TraceColors.cyan,
              shape: BoxShape.circle,
            ),
          ),
          Expanded(child: Text(bullet)),
        ],
      );
    }

    return Text(line);
  }
}

class _HeroSlideData {
  const _HeroSlideData({
    required this.kicker,
    required this.title,
    required this.subtitle,
    required this.icon,
  });

  final String kicker;
  final String title;
  final String subtitle;
  final IconData icon;
}

class _HeroCarousel extends StatefulWidget {
  const _HeroCarousel();

  @override
  State<_HeroCarousel> createState() => _HeroCarouselState();
}

class _HeroCarouselState extends State<_HeroCarousel> {
  static const _slides = [
    _HeroSlideData(
      kicker: '快速了解',
      title: 'BLE\nMonitor',
      subtitle: '连接、监控、记录',
      icon: Icons.bluetooth_connected,
    ),
    _HeroSlideData(
      kicker: '实时监控',
      title: '功率\n数据',
      subtitle: '广播解析、功耗统计',
      icon: Icons.bolt,
    ),
    _HeroSlideData(
      kicker: '设备管理',
      title: '码表\n遥控',
      subtitle: '骑行数据、蓝牙控制',
      icon: Icons.directions_bike,
    ),
  ];

  final PageController _controller = PageController();
  int _index = 0;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 190,
      child: PageView.builder(
        controller: _controller,
        physics: const BouncingScrollPhysics(),
        onPageChanged: (index) {
          setState(() {
            _index = index;
          });
        },
        itemCount: _slides.length,
        itemBuilder: (context, index) {
          return Padding(
            padding: EdgeInsets.only(right: index == _slides.length - 1 ? 0 : 10),
            child: _HeroCard(
              data: _slides[index],
              activeIndex: _index,
              slideCount: _slides.length,
            ),
          );
        },
      ),
    );
  }
}

/// “快速了解 BLE Monitor” 英雄卡，右侧为纯代码绘制的手机插画
class _HeroCard extends StatelessWidget {
  const _HeroCard({
    required this.data,
    required this.activeIndex,
    required this.slideCount,
  });

  final _HeroSlideData data;
  final int activeIndex;
  final int slideCount;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(18, 18, 14, 12),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            Color(0xFF0A2A36),
            Color(0xFF07202B),
            Color(0xFF051620),
          ],
        ),
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: TraceColors.cyan.withOpacity(0.3)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.4),
            blurRadius: 26,
            offset: const Offset(0, 14),
          ),
          BoxShadow(
            color: TraceColors.cyan.withOpacity(0.16),
            blurRadius: 30,
            spreadRadius: -10,
          ),
        ],
      ),
      child: Column(
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Container(
                          width: 3,
                          height: 13,
                          decoration: BoxDecoration(
                            color: TraceColors.cyan,
                            borderRadius: BorderRadius.circular(2),
                            boxShadow: [
                              BoxShadow(
                                color: TraceColors.cyan.withOpacity(0.7),
                                blurRadius: 6,
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(width: 8),
                        Text(
                          data.kicker,
                          style: TextStyle(
                            color: TraceColors.cyan,
                            fontSize: 13,
                            fontWeight: FontWeight.w700,
                            letterSpacing: 1.2,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    Text(
                      data.title,
                      style: TextStyle(
                        color: TraceColors.text,
                        fontSize: 28,
                        height: 1.08,
                        fontWeight: FontWeight.w900,
                        letterSpacing: 0.4,
                        shadows: [
                          Shadow(color: Color(0x5524F6DE), blurRadius: 14),
                        ],
                      ),
                    ),
                    const SizedBox(height: 10),
                    Row(
                      children: [
                        Icon(
                          data.icon,
                          size: 14,
                          color: TraceColors.muted.withOpacity(0.9),
                        ),
                        const SizedBox(width: 6),
                        Text(
                          data.subtitle,
                          style: TextStyle(
                            color: TraceColors.muted.withOpacity(0.95),
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                            letterSpacing: 1,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              const SizedBox(
                width: 112,
                height: 126,
                child: _HeroPhoneArt(),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              for (var i = 0; i < slideCount; i++) ...[
                if (i != 0) const SizedBox(width: 6),
                AnimatedContainer(
                  duration: const Duration(milliseconds: 220),
                  width: i == activeIndex ? 16 : 4,
                  height: 4,
                  decoration: BoxDecoration(
                    color: i == activeIndex
                        ? TraceColors.cyan
                        : TraceColors.muted.withOpacity(0.35),
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ],
            ],
          ),
        ],
      ),
    );
  }
}

/// 手机样机插画：倾斜手机 + 屏内蓝牙与波形 + 背景光环
class _HeroPhoneArt extends StatelessWidget {
  const _HeroPhoneArt();

  @override
  Widget build(BuildContext context) {
    return Stack(
      alignment: Alignment.center,
      clipBehavior: Clip.none,
      children: [
        // 背景光环
        Container(
          width: 104,
          height: 104,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            gradient: RadialGradient(
              colors: [
                TraceColors.cyan.withOpacity(0.24),
                Colors.transparent,
              ],
            ),
          ),
        ),
        Positioned(
          left: 2,
          top: 10,
          child: Icon(
            Icons.bluetooth,
            size: 30,
            color: TraceColors.cyan.withOpacity(0.4),
          ),
        ),
        Transform.rotate(
          angle: -0.12,
          child: Container(
            width: 60,
            height: 112,
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [Color(0xFF0D303C), Color(0xFF04151D)],
              ),
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: TraceColors.cyan.withOpacity(0.55)),
              boxShadow: [
                BoxShadow(
                  color: TraceColors.cyan.withOpacity(0.3),
                  blurRadius: 22,
                  spreadRadius: -4,
                ),
                BoxShadow(
                  color: Colors.black.withOpacity(0.5),
                  blurRadius: 16,
                  offset: const Offset(4, 10),
                ),
              ],
            ),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Container(
                  width: 26,
                  height: 26,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: TraceColors.cyan.withOpacity(0.14),
                    border: Border.all(
                      color: TraceColors.cyan.withOpacity(0.7),
                    ),
                    boxShadow: [
                      BoxShadow(
                        color: TraceColors.cyan.withOpacity(0.5),
                        blurRadius: 12,
                      ),
                    ],
                  ),
                  child: const Icon(
                    Icons.bluetooth,
                    size: 15,
                    color: TraceColors.cyan,
                  ),
                ),
                const SizedBox(height: 12),
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    for (final barHeight in [7.0, 13.0, 9.0, 16.0, 11.0])
                      Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 1.6),
                        child: Container(
                          width: 3,
                          height: barHeight,
                          decoration: BoxDecoration(
                            color: TraceColors.cyan.withOpacity(0.8),
                            borderRadius: BorderRadius.circular(2),
                          ),
                        ),
                      ),
                  ],
                ),
                const SizedBox(height: 12),
                Container(
                  width: 22,
                  height: 3,
                  decoration: BoxDecoration(
                    color: TraceColors.muted.withOpacity(0.5),
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ],
            ),
          ),
        ),
        Positioned(
          right: 6,
          bottom: 8,
          child: Container(
            width: 5,
            height: 5,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: TraceColors.cyanSoft.withOpacity(0.8),
              boxShadow: [
                BoxShadow(
                  color: TraceColors.cyan.withOpacity(0.8),
                  blurRadius: 8,
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

class _GuideData {
  const _GuideData({
    required this.title,
    required this.icon,
    required this.points,
    required this.steps,
  });

  final String title;
  final IconData icon;
  final List<String> points;
  final List<String> steps;
}

class _GuideCard extends StatelessWidget {
  const _GuideCard({required this.data});

  final _GuideData data;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      borderRadius: BorderRadius.circular(18),
      child: InkWell(
        borderRadius: BorderRadius.circular(18),
        onTap: () => DiscoverTabPage._showGuideDialog(data),
        child: Ink(
          width: 150,
          padding: const EdgeInsets.fromLTRB(14, 16, 14, 12),
          decoration: BoxDecoration(
            color: const Color(0xFF071B25).withOpacity(0.82),
            borderRadius: BorderRadius.circular(18),
            border: Border.all(color: TraceColors.cyan.withOpacity(0.22)),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withOpacity(0.32),
                blurRadius: 20,
                offset: const Offset(0, 12),
              ),
              BoxShadow(
                color: TraceColors.cyan.withOpacity(0.1),
                blurRadius: 24,
                spreadRadius: -8,
              ),
            ],
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: const Color(0xFF04202B),
                  border: Border.all(
                    color: TraceColors.cyan.withOpacity(0.55),
                  ),
                  boxShadow: [
                    BoxShadow(
                      color: TraceColors.cyan.withOpacity(0.3),
                      blurRadius: 14,
                      spreadRadius: -2,
                    ),
                  ],
                ),
                child: Icon(data.icon, color: TraceColors.cyan, size: 21),
              ),
              const SizedBox(height: 12),
              Text(
                data.title,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                  color: TraceColors.text,
                  fontSize: 13.5,
                  fontWeight: FontWeight.w800,
                ),
              ),
              const SizedBox(height: 9),
              for (var i = 0; i < data.points.length; i++) ...[
                Row(
                  children: [
                    Container(
                      width: 3.5,
                      height: 3.5,
                      decoration: const BoxDecoration(
                        color: TraceColors.cyan,
                        shape: BoxShape.circle,
                      ),
                    ),
                    const SizedBox(width: 7),
                    Expanded(
                      child: Text(
                        data.points[i],
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          color: TraceColors.muted.withOpacity(0.95),
                          fontSize: 10.5,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                  ],
                ),
                if (i != data.points.length - 1) const SizedBox(height: 7),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _MoreRowData {
  const _MoreRowData({
    required this.title,
    required this.subtitle,
    required this.icon,
    required this.onTap,
  });

  final String title;
  final String subtitle;
  final IconData icon;
  final VoidCallback onTap;
}

class _MoreRow extends StatelessWidget {
  const _MoreRow({required this.data});

  final _MoreRowData data;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      borderRadius: BorderRadius.circular(16),
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: data.onTap,
        child: Ink(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
          decoration: BoxDecoration(
            color: const Color(0xFF071B25).withOpacity(0.72),
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: TraceColors.cyan.withOpacity(0.16)),
          ),
          child: Row(
            children: [
              Container(
                width: 42,
                height: 42,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: const Color(0xFF04202B),
                  border: Border.all(
                    color: TraceColors.cyan.withOpacity(0.45),
                  ),
                ),
                child: Icon(data.icon, color: TraceColors.cyan, size: 20),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      data.title,
                      style: const TextStyle(
                        color: TraceColors.text,
                        fontSize: 14.5,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    const SizedBox(height: 3),
                    Text(
                      data.subtitle,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        color: TraceColors.muted.withOpacity(0.85),
                        fontSize: 11,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              Icon(
                Icons.chevron_right,
                color: TraceColors.cyan.withOpacity(0.8),
                size: 20,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
