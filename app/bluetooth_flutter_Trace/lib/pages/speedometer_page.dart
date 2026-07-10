import 'dart:async';
import 'dart:convert';
import 'dart:io' as io;
import 'dart:math' as math;

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:get/get.dart';
import 'package:share_plus/share_plus.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../config/share_links.dart';
import '../controllers/ride_controller.dart';
import '../models/ride_models.dart';
import 'ota_upgrade_page.dart';

class SpeedometerPage extends StatefulWidget {
  const SpeedometerPage({super.key});

  @override
  State<SpeedometerPage> createState() => _SpeedometerPageState();
}

class _SpeedometerPageState extends State<SpeedometerPage> {
  @override
  Widget build(BuildContext context) {
    final controller = Get.isRegistered<RideController>()
        ? Get.find<RideController>()
        : Get.put(RideController());

    return MediaQuery(
      data: MediaQuery.of(context).copyWith(textScaler: TextScaler.noScaling),
      child: Scaffold(
      backgroundColor: _RideColors.background,
      body: SafeArea(
        bottom: false,
        child: Obx(() {
          final selectedIndex = controller.activeTabIndex.value;
          return Column(
            children: [
              // 固定顶部栏：永远可见、永远可点（不随内容滚动）
              Padding(
                padding: const EdgeInsets.fromLTRB(18, 12, 18, 0),
                child: _TopChrome(
                  selectedIndex: selectedIndex,
                  isConnected: selectedIndex != 3,
                ),
              ),
              // 选中页占满中间剩余空间，由各页自行决定固定子头与单一滚动区
              Expanded(
                child: _SelectedPage(
                  controller: controller,
                  selectedIndex: selectedIndex,
                ),
              ),
              // 记录中：可见的「结束并保存」入口（移动端与桌面均可点）
              if (controller.isRecording.value)
                _RecordingBar(controller: controller),
              // 固定底栏
              _RideTabBar(
                controller: controller,
                onSelect: controller.selectTab,
              ),
            ],
          );
        }),
      ),
      ),
    );
  }
}

class _SelectedPage extends StatelessWidget {
  const _SelectedPage({
    required this.controller,
    required this.selectedIndex,
  });

  final RideController controller;
  final int selectedIndex;

  @override
  Widget build(BuildContext context) {
    switch (selectedIndex) {
      case 1:
        return _StatisticsPage(controller: controller);
      case 2:
        return _RoutesPage(controller: controller);
      case 3:
        return _DevicesPage(controller: controller);
      case 0:
      default:
        return _DashboardPage(controller: controller);
    }
  }
}

class _TopChrome extends StatelessWidget {
  const _TopChrome({
    required this.selectedIndex,
    required this.isConnected,
  });

  final int selectedIndex;
  final bool isConnected;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 54,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: Align(
              alignment: Alignment.centerLeft,
              child: InkWell(
                borderRadius: BorderRadius.circular(12),
                onTap: _openConnectedDeviceDetail,
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(0, 4, 10, 6),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Container(
                        width: 24,
                        height: 38,
                        decoration: BoxDecoration(
                          borderRadius: BorderRadius.circular(5),
                          border: Border.all(
                            color: Colors.white.withOpacity(0.78),
                          ),
                        ),
                        child: const Icon(
                          Icons.more_vert,
                          color: Colors.white,
                          size: 15,
                        ),
                      ),
                      const SizedBox(width: 10),
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Text(
                            isConnected ? '已连接' : '未连接',
                            style: TextStyle(
                              color: Colors.white.withOpacity(0.90),
                              fontSize: 12,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                          const SizedBox(height: 2),
                          Text(
                            'iGPSPORT BSC300',
                            style: TextStyle(
                              color: Colors.white.withOpacity(0.70),
                              fontSize: 12,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
          Expanded(
            child: Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                IconButton(
                  onPressed: () => _showDeviceSyncActions(context),
                  icon: const Icon(
                    Icons.cloud_sync_outlined,
                    color: Colors.white,
                    size: 26,
                  ),
                ),
                IconButton(
                  onPressed: () => _showDeviceMoreActions(context),
                  icon: const Icon(
                    Icons.more_horiz,
                    color: Colors.white,
                    size: 25,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _DashboardPage extends StatelessWidget {
  const _DashboardPage({required this.controller});

  final RideController controller;

  @override
  Widget build(BuildContext context) {
    // LayoutBuilder 置于有界根（由父级 Expanded 给出有限高度），不在滚动体内测高。
    return LayoutBuilder(
      builder: (context, constraints) {
        return SingleChildScrollView(
          physics: const BouncingScrollPhysics(),
          padding: const EdgeInsets.fromLTRB(12, 12, 12, 12),
          child: ConstrainedBox(
            // 内容不足时填满视口、超出时可滚动，绝不溢出。
            constraints: BoxConstraints(
              minHeight: math.max(0.0, constraints.maxHeight - 24),
            ),
            child: Column(
              children: [
                _ActivityHeroCard(controller: controller),
                const SizedBox(height: 8),
                _DesignMetricGrid(controller: controller),
                const SizedBox(height: 8),
                _SpeedAltitudePanel(controller: controller),
                const SizedBox(height: 8),
                const _DistributionGrid(),
              ],
            ),
          ),
        );
      },
    );
  }
}

class _ActivityHeroCard extends StatelessWidget {
  const _ActivityHeroCard({required this.controller});

  final RideController controller;

  @override
  Widget build(BuildContext context) {
    return Obx(() {
      final sample = _RideSample.from(controller);
      final selectedRoute = controller.selectedRoute.value;
      final selectedGpxTrack = selectedRoute == null
          ? const <_GpxPoint>[]
          : _gpxPointsFromRideRoute(selectedRoute.track);
      final routeTitle = selectedRoute?.title ?? '户外骑行';
      final routeDate = selectedRoute?.date ??
          (controller.isRecording.value ? '当前骑行记录中' : '未选择路线');
      final gpsAccuracy = controller.gpsAccuracyM.value;
      final gpsUnit = gpsAccuracy > 0 ? '±${gpsAccuracy.toStringAsFixed(0)}m' : '';

      // 整张英雄卡可点击 → 进入当前选中的路线详情；
      // 全屏/分享圆钮为更内层 InkWell，点击时由最内层赢得手势，互不干扰。
      return GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: () {
          if (selectedRoute == null) {
            controller.selectTab(2);
            _showUiMessage('路线', '请先导入路线');
            return;
          }
          _openSelectedRideRoute(selectedRoute);
        },
        child: _GlassPanel(
        padding: const EdgeInsets.all(16),
        child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            height: 150,
            child: Stack(
              children: [
                // 地图：右上区域（不占满高度，给底部统计留出干净空间）
                Positioned(
                  top: 0,
                  right: 0,
                  width: 172,
                  height: 92,
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(14),
                    child: CustomPaint(
                      painter: _RouteMapPainter(
                        variant: selectedRoute?.variant ?? 0,
                        track: selectedRoute == null
                            ? controller.points
                            : const <RidePoint>[],
                        gpxTrack: selectedGpxTrack,
                      ),
                      child: const SizedBox.expand(),
                    ),
                  ),
                ),
                // 圆钮：地图右上角，最顶层，永远可点
                Positioned(
                  right: 6,
                  top: 6,
                  child: Column(
                    children: [
                      _RoundIconButton(
                        icon: Icons.fullscreen,
                        onTap: () => _openRidePage(
                          () => _RideFullscreenMapPage(
                            title: routeTitle,
                            date: routeDate,
                            distance: selectedRoute?.distance ??
                                sample.distanceText,
                            climb: selectedRoute?.climb ?? sample.climbText,
                            duration:
                                selectedRoute?.duration ?? sample.durationText,
                            variant: selectedRoute?.variant ?? 0,
                            track: selectedRoute == null
                                ? controller.points
                                : const <RidePoint>[],
                            gpxTrack: selectedGpxTrack,
                          ),
                        ),
                      ),
                      const SizedBox(height: 10),
                      _RoundIconButton(
                        icon: Icons.share_outlined,
                        onTap: () => _shareCurrentRide(context),
                      ),
                    ],
                  ),
                ),
                // 左上文字：户外骑行 + 日期 + 距离（限定在地图左侧）
                Positioned(
                  left: 0,
                  top: 2,
                  right: 184,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          const Icon(
                            Icons.directions_bike,
                            color: _RideColors.orange,
                            size: 17,
                          ),
                          const SizedBox(width: 7),
                          Text(
                            routeTitle,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: TextStyle(
                              color: Colors.white.withOpacity(0.96),
                              fontSize: 16,
                              fontWeight: FontWeight.w900,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 6),
                      Text(
                        routeDate,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          color: Colors.white.withOpacity(0.62),
                          fontSize: 12,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      const SizedBox(height: 6),
                      RichText(
                        text: TextSpan(
                          children: [
                            TextSpan(
                              text: sample.distanceText,
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 34,
                                height: 0.96,
                                fontWeight: FontWeight.w900,
                                letterSpacing: -1.2,
                              ),
                            ),
                            TextSpan(
                              text: ' km',
                              style: TextStyle(
                                color: Colors.white.withOpacity(0.92),
                                fontSize: 14,
                                fontWeight: FontWeight.w800,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
                // 底部统计：全宽四列，位于地图下方，互不重叠
                Positioned(
                  left: 0,
                  right: 0,
                  bottom: 0,
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(
                        child: _HeroStat(
                          label: '运动时间',
                          value: sample.durationText,
                          unit: '',
                        ),
                      ),
                      Expanded(
                        child: _HeroStat(
                          label: '平均速度',
                          value: sample.avgSpeedText,
                          unit: 'km/h',
                        ),
                      ),
                      Expanded(
                        child: _HeroStat(
                          label: '累计爬升',
                          value: sample.climbText,
                          unit: 'm',
                        ),
                      ),
                      Expanded(
                        child: _HeroStat(
                          label: 'GPS',
                          value: controller.gpsStatus.value,
                          unit: gpsUnit,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ],
        ),
        ),
      );
    });
  }
}

class _DesignMetricGrid extends StatelessWidget {
  const _DesignMetricGrid({required this.controller});

  final RideController controller;

  @override
  Widget build(BuildContext context) {
    return Obx(() {
      final sample = _RideSample.from(controller);
      final speedTrend = controller.speedTrendKmh.toList();
      final altitudeTrend = controller.altitudeTrendM.toList();
      final speedDetail = _MetricDetailData.speed(
        sample,
        speedTrend,
        controller.elapsed.value,
      );
      final powerDetail = _MetricDetailData.unavailable(
        icon: Icons.bolt,
        title: '功率',
        color: const Color(0xFF64D72A),
        primaryLabel: '平均功率',
        secondaryLabel: '最大功率',
        unit: 'w',
      );
      final heartRateDetail = _MetricDetailData.unavailable(
        icon: Icons.favorite,
        title: '心率',
        color: const Color(0xFFFF3B5F),
        primaryLabel: '平均心率',
        secondaryLabel: '最大心率',
        unit: 'bpm',
      );
      final cadenceDetail = _MetricDetailData.unavailable(
        icon: Icons.track_changes,
        title: '踏频',
        color: const Color(0xFFFFC400),
        primaryLabel: '平均踏频',
        secondaryLabel: '最高踏频',
        unit: 'rpm',
      );
      final climbDetail = _MetricDetailData.climb(
        sample,
        altitudeTrend,
        controller.elapsed.value,
      );
      final temperatureDetail = _MetricDetailData.unavailable(
        icon: Icons.thermostat,
        title: '温度',
        color: const Color(0xFF42D8E6),
        primaryLabel: '平均温度',
        secondaryLabel: '最高温度',
        unit: '°C',
      );
      final cards = [
        _MetricTile(
          icon: Icons.speed,
          color: const Color(0xFF2088FF),
          title: '平均速度',
          value: sample.avgSpeedText,
          unit: 'km/h',
          footnote: '最高 ${sample.maxSpeedText} km/h',
          sparkColor: const Color(0xFF2088FF),
          values: speedTrend,
          onTap: () => _showMetricDetailDialog(context, speedDetail),
        ),
        _MetricTile(
          icon: Icons.bolt,
          color: const Color(0xFF64D72A),
          title: '平均功率',
          value: '--',
          unit: 'w',
          footnote: '暂无传感器数据',
          sparkColor: const Color(0xFF64D72A),
          values: const <double>[],
          onTap: () => _showMetricDetailDialog(context, powerDetail),
        ),
        _MetricTile(
          icon: Icons.favorite,
          color: const Color(0xFFFF3B5F),
          title: '平均心率',
          value: '--',
          unit: 'bpm',
          footnote: '暂无传感器数据',
          sparkColor: const Color(0xFFFF3B5F),
          values: const <double>[],
          onTap: () => _showMetricDetailDialog(context, heartRateDetail),
        ),
        _MetricTile(
          icon: Icons.track_changes,
          color: const Color(0xFFFFC400),
          title: '平均踏频',
          value: '--',
          unit: 'rpm',
          footnote: '暂无传感器数据',
          sparkColor: const Color(0xFFFFC400),
          values: const <double>[],
          onTap: () => _showMetricDetailDialog(context, cadenceDetail),
        ),
        _MetricTile(
          icon: Icons.terrain,
          color: const Color(0xFFA533FF),
          title: '累计爬升',
          value: sample.climbText,
          unit: 'm',
          footnote: '总上升 ${sample.climbText} m',
          sparkColor: const Color(0xFFA533FF),
          values: altitudeTrend,
          onTap: () => _showMetricDetailDialog(context, climbDetail),
        ),
        _MetricTile(
          icon: Icons.thermostat,
          color: const Color(0xFF42D8E6),
          title: '平均温度',
          value: '--',
          unit: '°C',
          footnote: '暂无传感器数据',
          sparkColor: const Color(0xFF42D8E6),
          values: const <double>[],
          onTap: () => _showMetricDetailDialog(context, temperatureDetail),
        ),
      ];

      return LayoutBuilder(
        builder: (context, constraints) {
          const columns = 3;
          const spacing = 8.0;
          final width =
              (constraints.maxWidth - spacing * (columns - 1)) / columns;
          return Wrap(
            spacing: spacing,
            runSpacing: spacing,
            children: [
              for (final card in cards) SizedBox(width: width, child: card),
            ],
          );
        },
      );
    });
  }
}

class _MetricTile extends StatelessWidget {
  const _MetricTile({
    required this.icon,
    required this.color,
    required this.title,
    required this.value,
    required this.unit,
    required this.footnote,
    required this.sparkColor,
    required this.values,
    required this.onTap,
  });

  final IconData icon;
  final Color color;
  final String title;
  final String value;
  final String unit;
  final String footnote;
  final Color sparkColor;
  final List<double> values;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      label: '$title 详情',
      child: MouseRegion(
        cursor: SystemMouseCursors.click,
        child: GestureDetector(
          behavior: HitTestBehavior.opaque,
          onTap: onTap,
          child: _GlassPanel(
            padding: const EdgeInsets.fromLTRB(8, 7, 8, 7),
            child: SizedBox(
              height: 80,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Container(
                        width: 18,
                        height: 18,
                        decoration: BoxDecoration(
                          color: color.withOpacity(0.13),
                          shape: BoxShape.circle,
                          border: Border.all(
                            color: color.withOpacity(0.90),
                            width: 1.2,
                          ),
                        ),
                        child: Icon(icon, color: color, size: 10),
                      ),
                      const SizedBox(width: 4),
                      Expanded(
                        child: SizedBox(
                          height: 14,
                          child: FittedBox(
                            fit: BoxFit.scaleDown,
                            alignment: Alignment.centerLeft,
                            child: Text(
                              title,
                              maxLines: 1,
                              softWrap: false,
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 11,
                                fontWeight: FontWeight.w800,
                              ),
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  RichText(
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    text: TextSpan(
                      children: [
                        TextSpan(
                          text: value,
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 17,
                            height: 1,
                            fontWeight: FontWeight.w900,
                            letterSpacing: -0.4,
                          ),
                        ),
                        TextSpan(
                          text: ' $unit',
                          style: TextStyle(
                            color: Colors.white.withOpacity(0.72),
                            fontSize: 10,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 2),
                  SizedBox(
                    height: 12,
                    width: double.infinity,
                    child: FittedBox(
                      fit: BoxFit.scaleDown,
                      alignment: Alignment.centerLeft,
                      child: Text(
                        footnote,
                        maxLines: 1,
                        softWrap: false,
                        style: TextStyle(
                          color: Colors.white.withOpacity(0.58),
                          fontSize: 10,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                  ),
                  const Spacer(),
                  SizedBox(
                    height: 12,
                    child: CustomPaint(
                      painter: _SparklinePainter(values: values, color: sparkColor),
                      child: const SizedBox.expand(),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _MetricDetailData {
  const _MetricDetailData({
    required this.icon,
    required this.title,
    required this.color,
    required this.primaryLabel,
    required this.primaryValue,
    required this.primaryUnit,
    required this.secondaryLabel,
    required this.secondaryValue,
    required this.secondaryUnit,
    required this.chartUnit,
    required this.chartMax,
    required this.chartTicks,
    required this.chartValues,
    required this.distributionTitle,
    required this.footerLabel,
    required this.footerValue,
    this.zones = const [],
    this.detailRows = const [],
    this.footerIcon,
    this.duration = Duration.zero,
  });

  final IconData icon;
  final String title;
  final Color color;
  final String primaryLabel;
  final String primaryValue;
  final String primaryUnit;
  final String secondaryLabel;
  final String secondaryValue;
  final String secondaryUnit;
  final String chartUnit;
  final double chartMax;
  final List<double> chartTicks;
  final List<double> chartValues;
  final String distributionTitle;
  final List<_MetricZoneRow> zones;
  final List<_MetricDetailRow> detailRows;
  final String footerLabel;
  final String footerValue;
  final IconData? footerIcon;
  final Duration duration;

  static _MetricDetailData unavailable({
    required IconData icon,
    required String title,
    required Color color,
    required String primaryLabel,
    required String secondaryLabel,
    required String unit,
  }) {
    return _MetricDetailData(
      icon: icon,
      title: title,
      color: color,
      primaryLabel: primaryLabel,
      primaryValue: '--',
      primaryUnit: unit,
      secondaryLabel: secondaryLabel,
      secondaryValue: '--',
      secondaryUnit: unit,
      chartUnit: unit,
      chartMax: 1,
      chartTicks: const <double>[0, 1],
      chartValues: const <double>[],
      distributionTitle: '数据分布',
      detailRows: const [
        _MetricDetailRow(label: '状态', value: '暂无实时传感器数据'),
      ],
      footerLabel: '数据来源',
      footerValue: '等待传感器接入',
    );
  }

  static _MetricDetailData speed(
    _RideSample sample,
    List<double> liveValues,
    Duration duration,
  ) {
    final hasSeries = liveValues.where((value) => value.isFinite).length >= 2;
    return _MetricDetailData(
      icon: Icons.speed,
      title: '速度',
      color: const Color(0xFF2088FF),
      primaryLabel: '平均速度',
      primaryValue: sample.avgSpeedText,
      primaryUnit: 'km/h',
      secondaryLabel: '最高速度',
      secondaryValue: sample.maxSpeedText,
      secondaryUnit: 'km/h',
      chartUnit: 'km/h',
      chartMax: 60,
      chartTicks: const <double>[0, 20, 40, 60],
      chartValues: _detailSeries(liveValues),
      distributionTitle: '速度分布',
      detailRows: [
        _MetricDetailRow(
          label: '状态',
          value: hasSeries ? '当前骑行 GPS 速度' : '等待实时速度数据',
        ),
      ],
      footerLabel: '数据来源',
      footerValue: hasSeries ? '当前骑行记录' : '等待 GPS 数据',
      duration: duration,
    );
  }

  static _MetricDetailData power() {
    return const _MetricDetailData(
      icon: Icons.bolt,
      title: '功率',
      color: Color(0xFF64D72A),
      primaryLabel: '平均功率',
      primaryValue: '186',
      primaryUnit: 'w',
      secondaryLabel: '最大功率',
      secondaryValue: '562',
      secondaryUnit: 'w',
      chartUnit: 'w',
      chartMax: 600,
      chartTicks: <double>[0, 200, 400, 600],
      chartValues: <double>[
        260, 300, 325, 345, 335, 360, 320, 380, 355, 390, 365, 430, 372, 470,
        520, 455, 562, 510, 445, 405, 435, 395, 410, 180, 430, 390, 415, 385,
        435, 405, 418, 392, 450, 405, 470, 330, 455, 390, 410, 480, 360,
      ],
      distributionTitle: '功率分布',
      zones: [
        _MetricZoneRow(
          color: Color(0xFFFF3158),
          zone: 'Z5',
          range: '> 350 w',
          value: '12:15',
          ratio: '11%',
        ),
        _MetricZoneRow(
          color: Color(0xFFFF7A1A),
          zone: 'Z4',
          range: '250 - 350 w',
          value: '28:47',
          ratio: '26%',
        ),
        _MetricZoneRow(
          color: Color(0xFFFFD21A),
          zone: 'Z3',
          range: '180 - 250 w',
          value: '40:21',
          ratio: '36%',
        ),
        _MetricZoneRow(
          color: Color(0xFF4AD14A),
          zone: 'Z2',
          range: '120 - 180 w',
          value: '32:16',
          ratio: '18%',
        ),
        _MetricZoneRow(
          color: Color(0xFF268DFF),
          zone: 'Z1',
          range: '< 120 w',
          value: '12:09',
          ratio: '9%',
        ),
      ],
      footerLabel: '归一化功率 (NP)',
      footerValue: '210 w',
    );
  }

  static _MetricDetailData heartRate() {
    return const _MetricDetailData(
      icon: Icons.favorite,
      title: '心率',
      color: Color(0xFFFF3B5F),
      primaryLabel: '平均心率',
      primaryValue: '156',
      primaryUnit: 'bpm',
      secondaryLabel: '最大心率',
      secondaryValue: '188',
      secondaryUnit: 'bpm',
      chartUnit: 'bpm',
      chartMax: 200,
      chartTicks: <double>[0, 50, 100, 150, 200],
      chartValues: <double>[
        88, 96, 92, 98, 94, 100, 110, 116, 125, 104, 126, 148, 160, 154, 166,
        158, 172, 164, 148, 134, 108, 146, 168, 176, 170, 182, 174, 168, 172,
        166, 148, 138, 142, 132, 150, 164, 158, 172, 152, 166, 156,
      ],
      distributionTitle: '心率分布',
      zones: [
        _MetricZoneRow(
          color: Color(0xFFFF3158),
          zone: 'Z5',
          range: '> 178 bpm',
          value: '08:36',
          ratio: '6%',
        ),
        _MetricZoneRow(
          color: Color(0xFFFF7A1A),
          zone: 'Z4',
          range: '160 - 178 bpm',
          value: '26:18',
          ratio: '17%',
        ),
        _MetricZoneRow(
          color: Color(0xFFFFD21A),
          zone: 'Z3',
          range: '140 - 160 bpm',
          value: '55:21',
          ratio: '36%',
        ),
        _MetricZoneRow(
          color: Color(0xFF4AD14A),
          zone: 'Z2',
          range: '120 - 140 bpm',
          value: '48:23',
          ratio: '31%',
        ),
        _MetricZoneRow(
          color: Color(0xFF268DFF),
          zone: 'Z1',
          range: '< 120 bpm',
          value: '11:10',
          ratio: '10%',
        ),
      ],
      footerLabel: '心率储备',
      footerValue: '63%',
    );
  }

  static _MetricDetailData cadence() {
    return const _MetricDetailData(
      icon: Icons.track_changes,
      title: '踏频',
      color: Color(0xFFFFC400),
      primaryLabel: '平均踏频',
      primaryValue: '87',
      primaryUnit: 'rpm',
      secondaryLabel: '最高踏频',
      secondaryValue: '118',
      secondaryUnit: 'rpm',
      chartUnit: 'rpm',
      chartMax: 150,
      chartTicks: <double>[0, 50, 100, 150],
      chartValues: <double>[
        78, 84, 88, 92, 96, 90, 104, 82, 88, 94, 86, 91, 97, 102, 90, 86, 93,
        98, 104, 100, 95, 108, 97, 102, 94, 99, 92, 101, 88, 96, 103, 94, 98,
        90, 100, 96, 104, 92, 101, 95, 106,
      ],
      distributionTitle: '踏频分布',
      zones: [
        _MetricZoneRow(
          color: Color(0xFFFF3158),
          zone: 'Z5',
          range: '> 110 rpm',
          value: '10:12',
          ratio: '9%',
        ),
        _MetricZoneRow(
          color: Color(0xFFFF7A1A),
          zone: 'Z4',
          range: '90 - 110 rpm',
          value: '28:33',
          ratio: '25%',
        ),
        _MetricZoneRow(
          color: Color(0xFFFFD21A),
          zone: 'Z3',
          range: '70 - 90 rpm',
          value: '45:18',
          ratio: '39%',
        ),
        _MetricZoneRow(
          color: Color(0xFF4AD14A),
          zone: 'Z2',
          range: '50 - 70 rpm',
          value: '32:45',
          ratio: '19%',
        ),
        _MetricZoneRow(
          color: Color(0xFF268DFF),
          zone: 'Z1',
          range: '< 50 rpm',
          value: '08:40',
          ratio: '8%',
        ),
      ],
      footerLabel: '最常用踏频',
      footerValue: '84 rpm',
    );
  }

  static _MetricDetailData climb(
    _RideSample sample,
    List<double> liveValues,
    Duration duration,
  ) {
    final cleaned = liveValues.where((value) => value.isFinite).toList();
    final hasSeries = cleaned.length >= 2;
    final currentAltitude =
        cleaned.isEmpty ? '--' : cleaned.last.toStringAsFixed(0);
    return _MetricDetailData(
      icon: Icons.terrain,
      title: '爬升',
      color: const Color(0xFFA533FF),
      primaryLabel: '累计爬升',
      primaryValue: sample.climbText,
      primaryUnit: 'm',
      secondaryLabel: '当前海拔',
      secondaryValue: currentAltitude,
      secondaryUnit: 'm',
      chartUnit: 'm',
      chartMax: 1500,
      chartTicks: const <double>[0, 500, 1000, 1500],
      chartValues: _detailSeries(liveValues),
      distributionTitle: '爬升分布',
      detailRows: [
        _MetricDetailRow(
          label: '状态',
          value: hasSeries ? '当前骑行 GPS 海拔' : '等待实时海拔数据',
        ),
      ],
      footerLabel: '数据来源',
      footerValue: hasSeries ? '当前骑行记录' : '等待 GPS 数据',
      duration: duration,
    );
  }

  static _MetricDetailData temperature() {
    return const _MetricDetailData(
      icon: Icons.thermostat,
      title: '温度',
      color: Color(0xFF23D8E9),
      primaryLabel: '平均温度',
      primaryValue: '22.4',
      primaryUnit: '°C',
      secondaryLabel: '最高温度',
      secondaryValue: '28.6',
      secondaryUnit: '°C',
      chartUnit: '°C',
      chartMax: 40,
      chartTicks: <double>[0, 10, 20, 30, 40],
      chartValues: <double>[
        24, 22, 24, 23, 22, 21, 20, 16, 15, 14, 15, 13, 14, 12, 13, 11, 15,
        18, 21, 22, 24, 26, 18, 17, 19, 18, 17, 15, 16, 18, 20, 23, 18,
      ],
      distributionTitle: '',
      detailRows: [
        _MetricDetailRow(label: '最低温度', value: '18.2 °C'),
        _MetricDetailRow(label: '温差', value: '10.4 °C'),
        _MetricDetailRow(label: '高温时长 (>25°C)', value: '1:12:38    32%'),
        _MetricDetailRow(label: '低温时长 (<15°C)', value: '00:00:00    0%'),
      ],
      footerLabel: '温度趋势',
      footerValue: '缓慢升高',
      footerIcon: Icons.north_east,
    );
  }
}

class _MetricZoneRow {
  const _MetricZoneRow({
    required this.color,
    required this.zone,
    required this.range,
    required this.value,
    required this.ratio,
  });

  final Color color;
  final String zone;
  final String range;
  final String value;
  final String ratio;
}

class _MetricDetailRow {
  const _MetricDetailRow({
    required this.label,
    required this.value,
  });

  final String label;
  final String value;
}

List<double> _detailSeries(List<double> liveValues) {
  final cleaned = liveValues.where((value) => value.isFinite).toList();
  return cleaned.length >= 2 ? cleaned : const <double>[];
}

void _showMetricDetailDialog(BuildContext context, _MetricDetailData data) {
  showGeneralDialog<void>(
    context: context,
    barrierDismissible: true,
    barrierLabel: MaterialLocalizations.of(context).modalBarrierDismissLabel,
    barrierColor: Colors.black.withOpacity(0.62),
    transitionDuration: const Duration(milliseconds: 220),
    pageBuilder: (context, animation, secondaryAnimation) {
      return _MetricDetailDialog(data: data);
    },
    transitionBuilder: (context, animation, secondaryAnimation, child) {
      final curved = CurvedAnimation(
        parent: animation,
        curve: Curves.easeOutCubic,
        reverseCurve: Curves.easeInCubic,
      );
      return FadeTransition(
        opacity: curved,
        child: ScaleTransition(
          scale: Tween<double>(begin: 0.96, end: 1).animate(curved),
          child: child,
        ),
      );
    },
  );
}

class _MetricDetailDialog extends StatelessWidget {
  const _MetricDetailDialog({required this.data});

  final _MetricDetailData data;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 18),
          child: LayoutBuilder(
            builder: (context, constraints) {
              final maxHeight = math.min(746.0, constraints.maxHeight);
              return Center(
                child: ConstrainedBox(
                  constraints: BoxConstraints(
                    maxWidth: 520,
                    maxHeight: maxHeight,
                  ),
                  child: _MetricDetailPanel(data: data),
                ),
              );
            },
          ),
        ),
      ),
    );
  }
}

class _MetricDetailPanel extends StatelessWidget {
  const _MetricDetailPanel({required this.data});

  final _MetricDetailData data;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.white.withOpacity(0.10)),
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            const Color(0xFF202A36).withOpacity(0.98),
            const Color(0xFF121922).withOpacity(0.99),
          ],
        ),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.46),
            blurRadius: 34,
            offset: const Offset(0, 20),
          ),
        ],
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(12),
        child: SingleChildScrollView(
          physics: const BouncingScrollPhysics(),
          padding: const EdgeInsets.fromLTRB(18, 16, 18, 20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              _MetricDetailHeader(data: data),
              const SizedBox(height: 22),
              _MetricDetailStats(data: data),
              const SizedBox(height: 20),
              SizedBox(
                height: 190,
                child: _InteractiveMetricAreaChart(data: data),
              ),
              const SizedBox(height: 18),
              if (data.zones.isNotEmpty)
                _MetricDistributionBox(data: data)
              else
                _MetricDetailRowsBox(rows: data.detailRows),
              const SizedBox(height: 20),
              _MetricDetailFooter(data: data),
            ],
          ),
        ),
      ),
    );
  }
}

class _MetricDetailHeader extends StatelessWidget {
  const _MetricDetailHeader({required this.data});

  final _MetricDetailData data;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 42,
      child: Stack(
        alignment: Alignment.center,
        children: [
          Align(
            alignment: Alignment.centerLeft,
            child: IconButton(
              onPressed: () => Navigator.of(context).pop(),
              padding: EdgeInsets.zero,
              constraints: const BoxConstraints.tightFor(width: 40, height: 40),
              icon: Icon(
                Icons.close,
                color: Colors.white.withOpacity(0.62),
                size: 30,
              ),
            ),
          ),
          Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 34,
                height: 34,
                decoration: BoxDecoration(
                  color: data.color.withOpacity(0.13),
                  shape: BoxShape.circle,
                  border: Border.all(color: data.color, width: 2),
                ),
                child: Icon(data.icon, color: data.color, size: 20),
              ),
              const SizedBox(width: 12),
              Text(
                data.title,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 25,
                  fontWeight: FontWeight.w900,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _MetricDetailStats extends StatelessWidget {
  const _MetricDetailStats({required this.data});

  final _MetricDetailData data;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: _MetricDetailStat(
            label: data.primaryLabel,
            value: data.primaryValue,
            unit: data.primaryUnit,
          ),
        ),
        const SizedBox(width: 18),
        Expanded(
          child: _MetricDetailStat(
            label: data.secondaryLabel,
            value: data.secondaryValue,
            unit: data.secondaryUnit,
          ),
        ),
      ],
    );
  }
}

class _MetricDetailStat extends StatelessWidget {
  const _MetricDetailStat({
    required this.label,
    required this.value,
    required this.unit,
  });

  final String label;
  final String value;
  final String unit;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: TextStyle(
            color: Colors.white.withOpacity(0.55),
            fontSize: 15,
            fontWeight: FontWeight.w700,
          ),
        ),
        const SizedBox(height: 8),
        FittedBox(
          fit: BoxFit.scaleDown,
          alignment: Alignment.centerLeft,
          child: RichText(
            maxLines: 1,
            text: TextSpan(
              children: [
                TextSpan(
                  text: value,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 30,
                    height: 1,
                    fontWeight: FontWeight.w900,
                    letterSpacing: -0.6,
                  ),
                ),
                TextSpan(
                  text: ' $unit',
                  style: TextStyle(
                    color: Colors.white.withOpacity(0.70),
                    fontSize: 15,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

class _MetricDistributionBox extends StatelessWidget {
  const _MetricDistributionBox({required this.data});

  final _MetricDetailData data;

  @override
  Widget build(BuildContext context) {
    final distribution = data.zones
        .map((zone) => double.parse(zone.ratio.replaceAll('%', '')) / 100)
        .toList();
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(16, 14, 16, 16),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.015),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.white.withOpacity(0.08)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            data.distributionTitle,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 20,
              fontWeight: FontWeight.w900,
            ),
          ),
          const SizedBox(height: 16),
          LayoutBuilder(
            builder: (context, constraints) {
              final donutSize = constraints.maxWidth < 390 ? 96.0 : 116.0;
              return Row(
                crossAxisAlignment: CrossAxisAlignment.center,
                children: [
                  Expanded(
                    child: Column(
                      children: [
                        for (final zone in data.zones)
                          Padding(
                            padding: const EdgeInsets.only(bottom: 9),
                            child: _MetricZoneLine(zone: zone),
                          ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 16),
                  _InteractiveDonutChart(
                    size: donutSize,
                    strokeWidth: donutSize < 100 ? 14 : 18,
                    colors: data.zones.map((zone) => zone.color).toList(),
                    values: distribution,
                    labels: data.zones
                        .map((zone) => zone.zone.isEmpty
                            ? zone.range
                            : '${zone.zone} ${zone.range}')
                        .toList(),
                    details: data.zones
                        .map((zone) => '${zone.value}   ${zone.ratio}')
                        .toList(),
                    backgroundColor: const Color(0xFF171D27),
                    center: const SizedBox.shrink(),
                  ),
                ],
              );
            },
          ),
        ],
      ),
    );
  }
}

class _MetricZoneLine extends StatelessWidget {
  const _MetricZoneLine({required this.zone});

  final _MetricZoneRow zone;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 14,
          height: 14,
          decoration: BoxDecoration(
            color: zone.color,
            borderRadius: BorderRadius.circular(3),
          ),
        ),
        if (zone.zone.isNotEmpty) ...[
          const SizedBox(width: 7),
          Text(
            zone.zone,
            style: TextStyle(
              color: zone.color,
              fontSize: 14,
              fontWeight: FontWeight.w900,
            ),
          ),
        ],
        const SizedBox(width: 7),
        Expanded(
          child: Text(
            zone.range,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(
              color: Colors.white.withOpacity(0.58),
              fontSize: 14,
              fontWeight: FontWeight.w700,
            ),
          ),
        ),
        const SizedBox(width: 8),
        SizedBox(
          width: 58,
          height: 17,
          child: FittedBox(
            fit: BoxFit.scaleDown,
            alignment: Alignment.centerRight,
            child: Text(
              zone.value,
              textAlign: TextAlign.right,
              maxLines: 1,
              softWrap: false,
              style: TextStyle(
                color: Colors.white.withOpacity(0.82),
                fontSize: 14,
                fontWeight: FontWeight.w800,
              ),
            ),
          ),
        ),
        const SizedBox(width: 6),
        SizedBox(
          width: 44,
          height: 17,
          child: FittedBox(
            fit: BoxFit.scaleDown,
            alignment: Alignment.centerRight,
            child: Text(
              zone.ratio,
              textAlign: TextAlign.right,
              maxLines: 1,
              softWrap: false,
              style: TextStyle(
                color: Colors.white.withOpacity(0.64),
                fontSize: 14,
                fontWeight: FontWeight.w800,
              ),
            ),
          ),
        ),
      ],
    );
  }
}

class _MetricDetailRowsBox extends StatelessWidget {
  const _MetricDetailRowsBox({required this.rows});

  final List<_MetricDetailRow> rows;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(22, 20, 22, 22),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.015),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.white.withOpacity(0.08)),
      ),
      child: Column(
        children: [
          for (final row in rows)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 9),
              child: Row(
                children: [
                  Expanded(
                    flex: 3,
                    child: SizedBox(
                      height: 19,
                      child: FittedBox(
                        fit: BoxFit.scaleDown,
                        alignment: Alignment.centerLeft,
                        child: Text(
                          row.label,
                          maxLines: 1,
                          softWrap: false,
                          style: TextStyle(
                            color: Colors.white.withOpacity(0.55),
                            fontSize: 16,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    flex: 2,
                    child: SizedBox(
                      height: 19,
                      child: FittedBox(
                        fit: BoxFit.scaleDown,
                        alignment: Alignment.centerRight,
                        child: Text(
                          row.value,
                          textAlign: TextAlign.right,
                          maxLines: 1,
                          softWrap: false,
                          style: TextStyle(
                            color: Colors.white.withOpacity(0.82),
                            fontSize: 16,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

class _MetricDetailFooter extends StatelessWidget {
  const _MetricDetailFooter({required this.data});

  final _MetricDetailData data;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: Text(
            data.footerLabel,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(
              color: Colors.white.withOpacity(0.70),
              fontSize: 16,
              fontWeight: FontWeight.w800,
            ),
          ),
        ),
        const SizedBox(width: 12),
        Flexible(
          child: Text(
            data.footerValue,
            textAlign: TextAlign.right,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(
              color: Colors.white.withOpacity(0.88),
              fontSize: 17,
              fontWeight: FontWeight.w800,
            ),
          ),
        ),
        if (data.footerIcon != null) ...[
          const SizedBox(width: 10),
          Icon(data.footerIcon, color: Colors.white.withOpacity(0.62), size: 20),
        ],
      ],
    );
  }
}

class _InteractiveMetricAreaChart extends StatefulWidget {
  const _InteractiveMetricAreaChart({required this.data});

  final _MetricDetailData data;

  @override
  State<_InteractiveMetricAreaChart> createState() =>
      _InteractiveMetricAreaChartState();
}

class _InteractiveMetricAreaChartState
    extends State<_InteractiveMetricAreaChart> {
  Timer? _hideTimer;
  int? _selectedIndex;

  @override
  void dispose() {
    _hideTimer?.cancel();
    super.dispose();
  }

  void _hideSelection() {
    if (_selectedIndex == null) return;
    _hideTimer?.cancel();
    setState(() => _selectedIndex = null);
  }

  void _selectAt(Offset localPosition, Size size) {
    final index = _indexForPosition(localPosition, size);
    if (index == null) {
      _hideSelection();
      return;
    }
    _hideTimer?.cancel();
    setState(() => _selectedIndex = index);
    _hideTimer = Timer(const Duration(seconds: 3), () {
      if (mounted) setState(() => _selectedIndex = null);
    });
  }

  int? _indexForPosition(Offset localPosition, Size size) {
    final values = widget.data.chartValues;
    if (values.length < 2) return null;
    final rect = _metricAreaChartRect(size);
    final t =
        ((localPosition.dx - rect.left) / rect.width).clamp(0.0, 1.0).toDouble();
    return (t * (values.length - 1))
        .round()
        .clamp(0, values.length - 1)
        .toInt();
  }

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final size = Size(constraints.maxWidth, constraints.maxHeight);
        return TapRegion(
          onTapOutside: (_) => _hideSelection(),
          child: Listener(
            behavior: HitTestBehavior.opaque,
            onPointerDown: (event) => _selectAt(event.localPosition, size),
            onPointerMove: (event) => _selectAt(event.localPosition, size),
            child: CustomPaint(
              painter: _MetricAreaChartPainter(
                data: widget.data,
                selectedIndex: _selectedIndex,
              ),
              child: const SizedBox.expand(),
            ),
          ),
        );
      },
    );
  }
}

Rect _metricAreaChartRect(Size size) =>
    Rect.fromLTRB(42, 28, size.width - 12, size.height - 26);

class _MetricAreaChartPainter extends CustomPainter {
  const _MetricAreaChartPainter({
    required this.data,
    this.selectedIndex,
  });

  final _MetricDetailData data;
  final int? selectedIndex;

  @override
  void paint(Canvas canvas, Size size) {
    if (data.chartValues.length < 2 || data.chartMax <= 0) return;
    final chartRect = _metricAreaChartRect(size);
    final gridPaint = Paint()
      ..color = Colors.white.withOpacity(0.075)
      ..strokeWidth = 1;

    _drawText(
      canvas,
      data.chartUnit,
      Offset(0, 2),
      color: Colors.white.withOpacity(0.56),
      size: 13,
      bold: true,
    );

    for (final tick in data.chartTicks) {
      final y = chartRect.bottom -
          chartRect.height * (tick / data.chartMax).clamp(0.0, 1.0);
      canvas.drawLine(Offset(chartRect.left, y), Offset(chartRect.right, y), gridPaint);
      _drawText(
        canvas,
        tick.toStringAsFixed(0),
        Offset(6, y - 8),
        color: Colors.white.withOpacity(0.48),
        size: 13,
      );
    }

    final path = Path();
    for (var i = 0; i < data.chartValues.length; i++) {
      final value = data.chartValues[i].clamp(0.0, data.chartMax).toDouble();
      final x = chartRect.left + chartRect.width * i / (data.chartValues.length - 1);
      final y = chartRect.bottom - chartRect.height * value / data.chartMax;
      if (i == 0) {
        path.moveTo(x, y);
      } else {
        path.lineTo(x, y);
      }
    }

    final fill = Path.from(path)
      ..lineTo(chartRect.right, chartRect.bottom)
      ..lineTo(chartRect.left, chartRect.bottom)
      ..close();
    canvas.drawPath(
      fill,
      Paint()
        ..shader = LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [
            data.color.withOpacity(0.45),
            data.color.withOpacity(0.06),
            data.color.withOpacity(0.0),
          ],
        ).createShader(chartRect),
    );
    canvas.drawPath(
      path,
      Paint()
        ..color = data.color
        ..strokeWidth = 2.2
        ..style = PaintingStyle.stroke
        ..strokeCap = StrokeCap.round
        ..strokeJoin = StrokeJoin.round,
    );

    final labels = _timeAxisLabels(data.duration, count: 5);
    for (var i = 0; i < labels.length; i++) {
      final x = chartRect.left + chartRect.width * i / (labels.length - 1);
      _drawText(
        canvas,
        labels[i],
        Offset(x, size.height - 14),
        color: Colors.white.withOpacity(0.52),
        size: 13,
        center: true,
        maxWidth: size.width,
      );
    }

    _drawSelection(canvas, size, chartRect);
  }

  void _drawSelection(Canvas canvas, Size size, Rect chartRect) {
    final index = selectedIndex;
    if (index == null || index < 0 || index >= data.chartValues.length) return;
    final value = data.chartValues[index].clamp(0.0, data.chartMax).toDouble();
    final x = chartRect.left + chartRect.width * index / (data.chartValues.length - 1);
    final y = chartRect.bottom - chartRect.height * value / data.chartMax;
    final point = Offset(x, y);

    canvas.drawLine(
      Offset(x, chartRect.top),
      Offset(x, chartRect.bottom),
      Paint()
        ..color = Colors.white.withOpacity(0.16)
        ..strokeWidth = 1,
    );
    canvas.drawCircle(
      point,
      6,
      Paint()
        ..color = data.color
        ..style = PaintingStyle.fill,
    );
    canvas.drawCircle(
      point,
      3,
      Paint()
        ..color = Colors.white.withOpacity(0.92)
        ..style = PaintingStyle.fill,
    );

    final valueText =
        '${_formatChartValue(value, data.chartUnit)} ${data.chartUnit}';
    final timeText =
        _timeLabelForIndex(index, data.chartValues.length, data.duration);
    _drawTooltip(
      canvas,
      anchor: point,
      size: size,
      title: timeText,
      value: valueText,
      accent: data.color,
    );
  }

  void _drawTooltip(
    Canvas canvas, {
    required Offset anchor,
    required Size size,
    required String title,
    required String value,
    required Color accent,
  }) {
    final titlePainter = _textPainter(
      title,
      color: Colors.white.withOpacity(0.66),
      size: 11,
      weight: FontWeight.w700,
    );
    final valuePainter = _textPainter(
      value,
      color: Colors.white,
      size: 13,
      weight: FontWeight.w900,
    );
    final width = math.max(titlePainter.width, valuePainter.width) + 24;
    const height = 48.0;
    final centerX = _clampDouble(anchor.dx, width / 2, size.width - width / 2);
    final top = _clampDouble(anchor.dy - height - 16, 6, size.height - height - 6);
    final rect = RRect.fromRectAndRadius(
      Rect.fromLTWH(centerX - width / 2, top, width, height),
      const Radius.circular(9),
    );
    canvas.drawRRect(
      rect,
      Paint()..color = const Color(0xFF303744).withOpacity(0.96),
    );
    canvas.drawRRect(
      rect,
      Paint()
        ..color = accent.withOpacity(0.32)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1,
    );
    titlePainter.paint(
      canvas,
      Offset(centerX - titlePainter.width / 2, top + 7),
    );
    valuePainter.paint(
      canvas,
      Offset(centerX - valuePainter.width / 2, top + 25),
    );
  }

  void _drawText(
    Canvas canvas,
    String text,
    Offset offset, {
    required Color color,
    required double size,
    bool bold = false,
    bool center = false,
    double? maxWidth,
  }) {
    final painter = TextPainter(
      text: TextSpan(
        text: text,
        style: TextStyle(
          color: color,
          fontSize: size,
          fontWeight: bold ? FontWeight.w900 : FontWeight.w700,
        ),
      ),
      textDirection: TextDirection.ltr,
    )..layout();
    var dx = offset.dx - (center ? painter.width / 2 : 0);
    if (maxWidth != null) {
      dx = dx.clamp(0.0, math.max(0.0, maxWidth - painter.width)).toDouble();
    }
    painter.paint(canvas, Offset(dx, offset.dy));
  }

  @override
  bool shouldRepaint(covariant _MetricAreaChartPainter oldDelegate) {
    return oldDelegate.data != data ||
        oldDelegate.selectedIndex != selectedIndex;
  }
}

class _ChartTooltipRow {
  const _ChartTooltipRow({
    required this.label,
    required this.value,
    required this.color,
  });

  final String label;
  final String value;
  final Color color;
}

class _SeriesSelection {
  const _SeriesSelection({
    required this.point,
    required this.value,
    required this.color,
  });

  final Offset point;
  final double value;
  final Color color;
}

TextPainter _textPainter(
  String text, {
  required Color color,
  required double size,
  required FontWeight weight,
}) {
  return TextPainter(
    text: TextSpan(
      text: text,
      style: TextStyle(
        color: color,
        fontSize: size,
        fontWeight: weight,
      ),
    ),
    textDirection: TextDirection.ltr,
  )..layout();
}

String _formatChartValue(double value, String unit) {
  if (unit == 'km/h' || unit == '°C') {
    return value.toStringAsFixed(1);
  }
  return value.round().toString();
}

double _clampDouble(double value, double min, double max) {
  if (max < min) return (min + max) / 2;
  return value.clamp(min, max).toDouble();
}

String _timeLabelForIndex(
  int index,
  int length, [
  Duration duration = Duration.zero,
]) {
  if (length <= 1) return '0:00';
  return _timeLabelForT(index / (length - 1), duration);
}

String _timeLabelForT(
  double t, [
  Duration duration = Duration.zero,
]) {
  final totalSeconds = math.max(0, duration.inSeconds);
  final seconds = (totalSeconds * t.clamp(0.0, 1.0)).round();
  final hours = seconds ~/ 3600;
  final minutes = (seconds % 3600) ~/ 60;
  final secs = seconds % 60;
  if (hours > 0) {
    return '$hours:${minutes.toString().padLeft(2, '0')}:${secs.toString().padLeft(2, '0')}';
  }
  return '$minutes:${secs.toString().padLeft(2, '0')}';
}

List<String> _timeAxisLabels(Duration duration, {required int count}) {
  final safeCount = math.max(2, count);
  return List.generate(
    safeCount,
    (index) => _timeLabelForT(index / (safeCount - 1), duration),
    growable: false,
  );
}

class _SpeedAltitudePanel extends StatelessWidget {
  const _SpeedAltitudePanel({required this.controller});

  final RideController controller;

  @override
  Widget build(BuildContext context) {
    return Obx(() {
      final sample = _RideSample.from(controller);
      final speedData = controller.speedTrendKmh.toList();
      final altitudeData = controller.altitudeTrendM.toList();

      return _GlassPanel(
        padding: const EdgeInsets.fromLTRB(8, 14, 8, 10),
        child: Column(
        children: [
          Wrap(
            spacing: 16,
            runSpacing: 6,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              const Text(
                '速度 & 海拔',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 16,
                  fontWeight: FontWeight.w900,
                ),
              ),
              _LegendText(
                label: '平均',
                value: '${sample.avgSpeedText} km/h',
                color: const Color(0xFF2B9DFF),
              ),
              _LegendText(
                label: '累计爬升',
                value: '${sample.climbText} m',
                color: const Color(0xFFA533FF),
              ),
            ],
          ),
          const SizedBox(height: 10),
          SizedBox(
            height: 116,
            child: _InteractiveDualLineChart(
              speed: speedData,
              altitude: altitudeData,
              duration: controller.elapsed.value,
            ),
          ),
        ],
        ),
      );
    });
  }
}

class _DistributionGrid extends StatelessWidget {
  const _DistributionGrid();

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final compact = constraints.maxWidth < 720;
        final panels = [
          const _ZoneDistributionPanel(
            title: '功率分布',
            summaryLabel: '平均功率',
            summaryValue: '-- w',
            centerText: '--',
            centerSubtext: '平均功率',
            colors: [
              Color(0xFF64D72A),
            ],
            labels: [
              '暂无实时传感器数据',
            ],
            values: ['等待传感器接入'],
            distribution: [1],
          ),
          const _ZoneDistributionPanel(
            title: '心率分布',
            summaryLabel: '平均心率',
            summaryValue: '-- bpm',
            centerText: '--',
            centerSubtext: '平均心率',
            colors: [
              Color(0xFFFF3B5F),
            ],
            labels: [
              '暂无实时传感器数据',
            ],
            values: ['等待传感器接入'],
            distribution: [1],
          ),
        ];

        if (compact) {
          return Column(
            children: [
              panels[0],
              const SizedBox(height: 8),
              panels[1],
            ],
          );
        }
        return Row(
          children: [
            Expanded(child: panels[0]),
            const SizedBox(width: 8),
            Expanded(child: panels[1]),
          ],
        );
      },
    );
  }
}

class _ZoneDistributionPanel extends StatelessWidget {
  const _ZoneDistributionPanel({
    required this.title,
    required this.summaryLabel,
    required this.summaryValue,
    required this.centerText,
    required this.centerSubtext,
    required this.colors,
    required this.labels,
    required this.values,
    required this.distribution,
  });

  final String title;
  final String summaryLabel;
  final String summaryValue;
  final String centerText;
  final String centerSubtext;
  final List<Color> colors;
  final List<String> labels;
  final List<String> values;
  final List<double> distribution;

  @override
  Widget build(BuildContext context) {
    return _GlassPanel(
      padding: const EdgeInsets.all(14),
      child: SizedBox(
        height: 124,
        child: Column(
          children: [
            Row(
              children: [
                Text(
                  title,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 16,
                    fontWeight: FontWeight.w900,
                  ),
                ),
                const Spacer(),
                _LegendText(
                  label: summaryLabel,
                  value: summaryValue,
                  color: title == '功率分布'
                      ? const Color(0xFF2B9DFF)
                      : const Color(0xFFA533FF),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Expanded(
              child: Row(
                children: [
                  _InteractiveDonutChart(
                    size: 70,
                    colors: colors,
                    values: distribution,
                    labels: labels,
                    details: values,
                    backgroundColor: _RideColors.panel,
                    center: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(
                          centerText,
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 18,
                            fontWeight: FontWeight.w900,
                          ),
                        ),
                        Text(
                          centerSubtext,
                          style: TextStyle(
                            color: Colors.white.withOpacity(0.50),
                            fontSize: 10,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        for (var i = 0; i < labels.length; i++)
                          Row(
                            children: [
                              Container(
                                width: 10,
                                height: 10,
                                decoration: BoxDecoration(
                                  color: colors[i],
                                  shape: BoxShape.circle,
                                ),
                              ),
                              const SizedBox(width: 7),
                              Expanded(
                                child: Text(
                                  labels[i],
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                  style: TextStyle(
                                    color: Colors.white.withOpacity(0.72),
                                    fontSize: 11,
                                    fontWeight: FontWeight.w700,
                                  ),
                                ),
                              ),
                              Text(
                                values[i],
                                style: TextStyle(
                                  color: Colors.white.withOpacity(0.82),
                                  fontSize: 11,
                                  fontWeight: FontWeight.w800,
                                ),
                              ),
                            ],
                          ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _StatisticsPage extends StatefulWidget {
  const _StatisticsPage({required this.controller});

  final RideController controller;

  @override
  State<_StatisticsPage> createState() => _StatisticsPageState();
}

class _StatisticsPageState extends State<_StatisticsPage> {
  static const _periodCount = 4;

  late final PageController _periodPageController;
  var _periodIndex = 1; // 0 周 / 1 月 / 2 年 / 3 全部
  late DateTime _selectedWeekStart;
  late DateTime _selectedMonth;
  late int _selectedYear;
  late DateTime _allStart;
  late DateTime _allEnd;

  String get _dateLabel {
    switch (_periodIndex) {
      case 0:
        return '${_formatSlashDate(_selectedWeekStart)} - '
            '${_formatSlashDate(_selectedWeekStart.add(const Duration(days: 6)))}';
      case 2:
        return '$_selectedYear年';
      case 3:
        return '${_formatSlashDate(_allStart)} - ${_formatSlashDate(_allEnd)}';
      case 1:
      default:
        return '${_selectedMonth.year}年${_selectedMonth.month}月';
    }
  }

  bool get _canShiftDate => _periodIndex != 3;

  @override
  void initState() {
    super.initState();
    final today = _dateOnly(DateTime.now());
    _selectedWeekStart = _weekStartSunday(today);
    _selectedMonth = DateTime(today.year, today.month);
    _selectedYear = today.year;
    _allStart = DateTime(today.year);
    _allEnd = today;
    _periodPageController = PageController(initialPage: _periodIndex);
  }

  @override
  void dispose() {
    _periodPageController.dispose();
    super.dispose();
  }

  void _selectPeriod(int index) {
    if (index < 0 || index >= _periodCount) return;
    if (index == _periodIndex) return;
    setState(() => _periodIndex = index);
    if (!_periodPageController.hasClients) return;
    unawaited(
      _periodPageController.animateToPage(
        index,
        duration: const Duration(milliseconds: 220),
        curve: Curves.easeOutCubic,
      ),
    );
  }

  void _handlePeriodPageChanged(int index) {
    if (index == _periodIndex) return;
    setState(() => _periodIndex = index);
  }

  void _shiftDate(int delta) {
    if (!_canShiftDate) return;
    setState(() {
      switch (_periodIndex) {
        case 0:
          _selectedWeekStart =
              _selectedWeekStart.add(Duration(days: 7 * delta));
          break;
        case 2:
          _selectedYear += delta;
          break;
        case 1:
        default:
          _selectedMonth = DateTime(
            _selectedMonth.year,
            _selectedMonth.month + delta,
          );
          break;
      }
    });
  }

  Future<void> _openDatePicker() async {
    switch (_periodIndex) {
      case 0:
        final selected = await _showStatsWeekPicker(
          context,
          initialWeekStart: _selectedWeekStart,
        );
        if (selected != null && mounted) {
          setState(() => _selectedWeekStart = selected);
        }
        break;
      case 2:
        final selected = await _showStatsYearPicker(
          context,
          initialYear: _selectedYear,
        );
        if (selected != null && mounted) {
          setState(() => _selectedYear = selected);
        }
        break;
      case 3:
        final selected = await _showStatsAllPicker(
          context,
          initialStart: _allStart,
          initialEnd: _allEnd,
        );
        if (selected != null && mounted) {
          setState(() {
            _allStart = selected.start;
            _allEnd = selected.end;
          });
        }
        break;
      case 1:
      default:
        final selected = await _showStatsMonthPicker(
          context,
          initialMonth: _selectedMonth,
        );
        if (selected != null && mounted) {
          setState(() => _selectedMonth = selected);
        }
        break;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Obx(() {
      final rides = widget.controller.rideHistory.toList();
      return Column(
        children: [
          // 固定子头：周期分段 + 日期选择器（无第二顶部栏）
          Padding(
            padding: const EdgeInsets.fromLTRB(18, 12, 18, 6),
            child: Column(
              children: [
                _PeriodSegment(
                  selectedIndex: _periodIndex,
                  controller: _periodPageController,
                  onSelect: _selectPeriod,
                ),
                const SizedBox(height: 14),
                _MonthSelector(
                  label: _dateLabel,
                  canShift: _canShiftDate,
                  onPrevious: () => _shiftDate(-1),
                  onNext: () => _shiftDate(1),
                  onTapLabel: _openDatePicker,
                ),
              ],
            ),
          ),
          // 单一滚动区：按周期切换面板
          Expanded(
            child: PageView.builder(
              controller: _periodPageController,
              physics: const PageScrollPhysics(
                parent: BouncingScrollPhysics(),
              ),
              itemCount: _periodCount,
              onPageChanged: _handlePeriodPageChanged,
              itemBuilder: (context, index) {
                return SingleChildScrollView(
                  physics: const BouncingScrollPhysics(),
                  padding: const EdgeInsets.fromLTRB(18, 8, 18, 16),
                  child: Column(children: _panelsForPeriod(index, rides)),
                );
              },
            ),
          ),
        ],
      );
    });
  }

  List<Widget> _panelsForPeriod(int index, List<RideSession> rides) {
    switch (index) {
      case 0:
        return _trendPanels(rides, isWeek: true);
      case 2:
        return _yearPanels(rides);
      case 3:
        return _allPanels(rides);
      case 1:
      default:
        return _trendPanels(rides, isWeek: false);
    }
  }

  List<Widget> _trendPanels(List<RideSession> rides, {required bool isWeek}) {
    final dates = isWeek
        ? [
            for (var i = 0; i < 7; i++)
              _selectedWeekStart.add(Duration(days: i)),
          ]
        : _datesForMonth(_selectedMonth);
    final start = dates.first;
    final end = _exclusiveDayAfter(dates.last);
    final periodRides = _ridesInRange(rides, start, end);
    final labelIndices = isWeek
        ? [for (var i = 0; i < dates.length; i++) i]
        : _monthTickIndices(dates.length);
    final labels = isWeek
        ? [for (final date in dates) _weekdayLabel(date)]
        : [for (final index in labelIndices) _formatMonthDayTick(dates[index])];
    final tooltipTitles = [
      for (final date in dates) _formatChineseMonthDay(date),
    ];
    final mileage = _dailyDistanceSeries(periodRides, dates);
    final duration = _dailyDurationSeries(periodRides, dates);
    return [
      _StatsOverview(stats: _RideStats.fromRides(periodRides)),
      const SizedBox(height: 12),
      _BarTrendPanel(
        title: '里程趋势',
        unit: '单位：km',
        values: mileage,
        labels: labels,
        labelIndices: labelIndices,
        color: _RideColors.orange,
        tooltipTitles: tooltipTitles,
        tooltipTitle: tooltipTitles.isEmpty ? '' : tooltipTitles.first,
        tooltipValue: '0.0 km',
        maxValue: _barMaxValue(mileage, fallback: isWeek ? 10.0 : 30.0),
      ),
      const SizedBox(height: 12),
      _BarTrendPanel(
        title: '运动时长趋势',
        unit: '单位：小时',
        values: duration,
        labels: labels,
        labelIndices: labelIndices,
        color: const Color(0xFF268DFF),
        tooltipTitles: tooltipTitles,
        tooltipTitle: tooltipTitles.isEmpty ? '' : tooltipTitles.first,
        tooltipValue: '0 分钟',
        maxValue: _barMaxValue(duration, fallback: isWeek ? 1.0 : 2.0),
      ),
    ];
  }
  // 年：运动类型分布 + 月度里程统计 + 月度时长统计 + 强度分布
  List<Widget> _yearPanels(List<RideSession> rides) {
    final yearStart = DateTime(_selectedYear);
    final yearEnd = DateTime(_selectedYear + 1);
    final yearRides = _ridesInRange(rides, yearStart, yearEnd);
    final monthMileage = _monthlyDistanceSeries(yearRides);
    final monthDuration = _monthlyDurationSeries(yearRides);
    const monthLabels = ['1月', '3月', '5月', '7月', '9月', '11月'];
    const monthLabelIndices = <int>[0, 2, 4, 6, 8, 10];
    final monthTooltipTitles = <String>[
      for (var month = 1; month <= 12; month++) '$month月',
    ];
    return [
      _AnnualDistributionPanel(outdoorDistanceKm: _sumDistance(yearRides)),
      const SizedBox(height: 12),
      _BarTrendPanel(
        title: '月度里程统计',
        unit: '单位：km',
        values: monthMileage,
        labels: monthLabels,
        labelIndices: monthLabelIndices,
        color: _RideColors.orange,
        tooltipTitles: monthTooltipTitles,
        tooltipTitle: '${DateTime.now().month}月',
        tooltipValue: '0.0 km',
        maxValue: _barMaxValue(monthMileage, fallback: 50.0),
      ),
      const SizedBox(height: 12),
      _BarTrendPanel(
        title: '月度时长统计',
        unit: '单位：小时',
        values: monthDuration,
        labels: monthLabels,
        labelIndices: monthLabelIndices,
        color: const Color(0xFF268DFF),
        tooltipTitles: monthTooltipTitles,
        tooltipTitle: '${DateTime.now().month}月',
        tooltipValue: '0 分钟',
        maxValue: _barMaxValue(monthDuration, fallback: 3.0),
      ),
      const SizedBox(height: 12),
      const _ZoneDistributionPanel(
        title: '强度分布',
        summaryLabel: '总时间',
        summaryValue: '149:48:00',
        centerText: '149:48',
        centerSubtext: '总时间',
        colors: [
          Color(0xFFFF3158),
          Color(0xFFFF7A1A),
          Color(0xFFFFD21A),
          Color(0xFF4AD14A),
          Color(0xFF268DFF),
        ],
        labels: [
          'Z5  > 178 bpm',
          'Z4  162 - 178 bpm',
          'Z3  140 - 160 bpm',
          'Z2  120 - 140 bpm',
          'Z1  < 120 bpm',
        ],
        values: ['08:36   6%', '26:18   17%', '55:21   36%', '48:23   31%', '11:10   10%'],
        distribution: [0.06, 0.17, 0.36, 0.31, 0.10],
      ),
    ];
  }

  // 全部：总览 + 运动类型分布 + 年度里程统计 + 年度时长统计
  List<Widget> _allPanels(List<RideSession> rides) {
    final rangeStart = _dateOnly(_allStart);
    final rangeEnd = _exclusiveDayAfter(_allEnd);
    final allRides = _ridesInRange(rides, rangeStart, rangeEnd);
    final years = _yearsForRange(rangeStart, _allEnd);
    final yearLabels = [for (final year in years) '$year'];
    final yearLabelIndices = [for (var i = 0; i < years.length; i++) i];
    final yearTooltipTitles = [for (final year in years) '$year年'];
    final yearMileage = _yearlyDistanceSeries(allRides, years);
    final yearDuration = _yearlyDurationSeries(allRides, years);
    return [
      _StatsOverview(stats: _RideStats.fromRides(allRides)),
      const SizedBox(height: 12),
      _AnnualDistributionPanel(outdoorDistanceKm: _sumDistance(allRides)),
      const SizedBox(height: 12),
      _BarTrendPanel(
        title: '年度里程统计',
        unit: '单位：km',
        values: yearMileage,
        labels: yearLabels,
        labelIndices: yearLabelIndices,
        color: _RideColors.orange,
        tooltipTitles: yearTooltipTitles,
        tooltipTitle: '${_selectedYear}年',
        tooltipValue: '0.0 km',
        maxValue: _barMaxValue(yearMileage, fallback: 50.0),
      ),
      const SizedBox(height: 12),
      _BarTrendPanel(
        title: '年度时长统计',
        unit: '单位：小时',
        values: yearDuration,
        labels: yearLabels,
        labelIndices: yearLabelIndices,
        color: const Color(0xFF268DFF),
        tooltipTitles: yearTooltipTitles,
        tooltipTitle: '${_selectedYear}年',
        tooltipValue: '0 分钟',
        maxValue: _barMaxValue(yearDuration, fallback: 3.0),
      ),
    ];
  }

}

class _PeriodSegment extends StatelessWidget {
  const _PeriodSegment({
    required this.selectedIndex,
    required this.controller,
    required this.onSelect,
  });

  final int selectedIndex;
  final PageController controller;
  final ValueChanged<int> onSelect;

  @override
  Widget build(BuildContext context) {
    const labels = ['周', '月', '年', '全部'];
    return Container(
      height: 47,
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.05),
        borderRadius: BorderRadius.circular(16),
      ),
      child: _AnimatedSegmentTabs(
        labels: labels,
        selectedIndex: selectedIndex,
        controller: controller,
        height: 39,
        borderRadius: BorderRadius.circular(14),
        indicatorColor: Colors.white.withOpacity(0.08),
        activeColor: Colors.white,
        inactiveColor: Colors.white.withOpacity(0.62),
        fontSize: 16,
        fontWeight: FontWeight.w800,
        onSelect: onSelect,
      ),
    );
  }
}

class _AnimatedSegmentTabs extends StatelessWidget {
  const _AnimatedSegmentTabs({
    required this.labels,
    required this.selectedIndex,
    required this.controller,
    required this.height,
    required this.borderRadius,
    required this.indicatorColor,
    required this.activeColor,
    required this.inactiveColor,
    required this.fontSize,
    required this.fontWeight,
    required this.onSelect,
    this.indicatorBorder,
  });

  final List<String> labels;
  final int selectedIndex;
  final PageController controller;
  final double height;
  final BorderRadius borderRadius;
  final Color indicatorColor;
  final Color activeColor;
  final Color inactiveColor;
  final double fontSize;
  final FontWeight fontWeight;
  final ValueChanged<int> onSelect;
  final Border? indicatorBorder;

  double _pagePosition() {
    if (labels.isEmpty) return 0;
    if (!controller.hasClients) return selectedIndex.toDouble();
    final page = controller.page ?? selectedIndex.toDouble();
    return page.clamp(0.0, labels.length - 1.0).toDouble();
  }

  @override
  Widget build(BuildContext context) {
    if (labels.isEmpty) return const SizedBox.shrink();
    return SizedBox(
      height: height,
      child: AnimatedBuilder(
        animation: controller,
        builder: (context, _) {
          final position = _pagePosition();
          return LayoutBuilder(
            builder: (context, constraints) {
              final tabWidth = constraints.maxWidth / labels.length;
              return Stack(
                children: [
                  Positioned(
                    left: tabWidth * position,
                    top: 0,
                    bottom: 0,
                    width: tabWidth,
                    child: DecoratedBox(
                      decoration: BoxDecoration(
                        color: indicatorColor,
                        borderRadius: borderRadius,
                        border: indicatorBorder,
                      ),
                    ),
                  ),
                  Row(
                    children: [
                      for (var i = 0; i < labels.length; i++)
                        Expanded(
                          child: InkWell(
                            borderRadius: borderRadius,
                            onTap: () => onSelect(i),
                            child: Center(
                              child: Padding(
                                padding:
                                    const EdgeInsets.symmetric(horizontal: 4),
                                child: FittedBox(
                                  fit: BoxFit.scaleDown,
                                  child: Text(
                                    labels[i],
                                    maxLines: 1,
                                    style: TextStyle(
                                      color: Color.lerp(
                                        inactiveColor,
                                        activeColor,
                                        (1 - (position - i).abs())
                                            .clamp(0.0, 1.0)
                                            .toDouble(),
                                      ),
                                      fontSize: fontSize,
                                      fontWeight: fontWeight,
                                    ),
                                  ),
                                ),
                              ),
                            ),
                          ),
                        ),
                    ],
                  ),
                ],
              );
            },
          );
        },
      ),
    );
  }
}

class _MonthSelector extends StatelessWidget {
  const _MonthSelector({
    required this.label,
    required this.canShift,
    required this.onPrevious,
    required this.onNext,
    required this.onTapLabel,
  });

  final String label;
  final bool canShift;
  final VoidCallback onPrevious;
  final VoidCallback onNext;
  final VoidCallback onTapLabel;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        IconButton(
          onPressed: canShift ? onPrevious : null,
          icon: Icon(
            Icons.chevron_left,
            color: Colors.white.withOpacity(canShift ? 0.86 : 0.24),
            size: 30,
          ),
        ),
        const SizedBox(width: 18),
        Flexible(
          child: InkWell(
            borderRadius: BorderRadius.circular(14),
            onTap: onTapLabel,
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              child: FittedBox(
                fit: BoxFit.scaleDown,
                child: Text(
                  label,
                  maxLines: 1,
                  softWrap: false,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 19,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
            ),
          ),
        ),
        const SizedBox(width: 18),
        IconButton(
          onPressed: canShift ? onNext : null,
          icon: Icon(
            Icons.chevron_right,
            color: Colors.white.withOpacity(canShift ? 0.86 : 0.24),
            size: 30,
          ),
        ),
      ],
    );
  }
}

class _StatsDateRange {
  const _StatsDateRange({
    required this.start,
    required this.end,
  });

  final DateTime start;
  final DateTime end;
}

Future<T?> _showStatsDialog<T>(
  BuildContext context,
  Widget child,
) {
  return showGeneralDialog<T>(
    context: context,
    barrierDismissible: true,
    barrierLabel: MaterialLocalizations.of(context).modalBarrierDismissLabel,
    barrierColor: Colors.black.withOpacity(0.58),
    transitionDuration: const Duration(milliseconds: 220),
    pageBuilder: (context, animation, secondaryAnimation) {
      return Material(
        color: Colors.transparent,
        child: SafeArea(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 18),
            child: Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 520),
                child: child,
              ),
            ),
          ),
        ),
      );
    },
    transitionBuilder: (context, animation, secondaryAnimation, child) {
      final curved = CurvedAnimation(
        parent: animation,
        curve: Curves.easeOutCubic,
        reverseCurve: Curves.easeInCubic,
      );
      return FadeTransition(
        opacity: curved,
        child: ScaleTransition(
          scale: Tween<double>(begin: 0.97, end: 1).animate(curved),
          child: child,
        ),
      );
    },
  );
}

Future<DateTime?> _showStatsWeekPicker(
  BuildContext context, {
  required DateTime initialWeekStart,
}) {
  var visibleMonth = DateTime(initialWeekStart.year, initialWeekStart.month);
  var pendingWeekStart = _weekStartSunday(initialWeekStart);

  return _showStatsDialog<DateTime>(
    context,
    StatefulBuilder(
      builder: (context, setDialogState) {
        return _StatsPickerFrame(
          title: '选择周',
          onConfirm: () => Navigator.of(context).pop(pendingWeekStart),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              _StatsMonthHeader(
                label: _formatChineseMonth(visibleMonth),
                onTapLabel: () async {
                  final selected = await _showStatsYearMonthPicker(
                    context,
                    initialMonth: visibleMonth,
                  );
                  if (selected == null) return;
                  setDialogState(() => visibleMonth = selected);
                },
                onPrevious: () => setDialogState(() {
                  visibleMonth = DateTime(
                    visibleMonth.year,
                    visibleMonth.month - 1,
                  );
                }),
                onNext: () => setDialogState(() {
                  visibleMonth = DateTime(
                    visibleMonth.year,
                    visibleMonth.month + 1,
                  );
                }),
              ),
              const SizedBox(height: 18),
              _StatsWeekCalendar(
                visibleMonth: visibleMonth,
                selectedWeekStart: pendingWeekStart,
                onSelect: (date) => setDialogState(() {
                  pendingWeekStart = _weekStartSunday(date);
                }),
              ),
              const SizedBox(height: 24),
              Text(
                '已选择：${_formatChineseDate(pendingWeekStart)} - '
                '${_formatChineseDate(pendingWeekStart.add(const Duration(days: 6)))}',
                textAlign: TextAlign.center,
                style: TextStyle(
                  color: Colors.white.withOpacity(0.72),
                  fontSize: 15,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ),
        );
      },
    ),
  );
}

Future<DateTime?> _showStatsMonthPicker(
  BuildContext context, {
  required DateTime initialMonth,
}) {
  var pending = DateTime(initialMonth.year, initialMonth.month);

  return _showStatsDialog<DateTime>(
    context,
    StatefulBuilder(
      builder: (context, setDialogState) {
        return _StatsPickerFrame(
          title: '选择月',
          onConfirm: () => Navigator.of(context).pop(pending),
          child: SizedBox(
            height: 360,
            child: _StatsScrollableMonthList(
              selectedMonth: pending,
              onSelect: (month) => setDialogState(() => pending = month),
            ),
          ),
        );
      },
    ),
  );
}

Future<int?> _showStatsYearPicker(
  BuildContext context, {
  required int initialYear,
}) {
  var pending = initialYear;

  return _showStatsDialog<int>(
    context,
    StatefulBuilder(
      builder: (context, setDialogState) {
        return _StatsPickerFrame(
          title: '选择年',
          onConfirm: () => Navigator.of(context).pop(pending),
          child: SizedBox(
            height: 390,
            child: _StatsScrollableYearList(
              selectedYear: pending,
              onSelect: (year) => setDialogState(() => pending = year),
            ),
          ),
        );
      },
    ),
  );
}

Future<DateTime?> _showStatsYearMonthPicker(
  BuildContext context, {
  required DateTime initialMonth,
}) {
  var pendingYear = initialMonth.year;
  var pendingMonth = initialMonth.month;

  return _showStatsDialog<DateTime>(
    context,
    StatefulBuilder(
      builder: (context, setDialogState) {
        return _StatsPickerFrame(
          title: '选择年月',
          onConfirm: () => Navigator.of(context).pop(
            DateTime(pendingYear, pendingMonth),
          ),
          child: SizedBox(
            height: 360,
            child: _StatsYearMonthWheelPicker(
              selectedYear: pendingYear,
              selectedMonth: pendingMonth,
              onYearChanged: (year) => setDialogState(() {
                pendingYear = year;
              }),
              onMonthChanged: (month) => setDialogState(() {
                pendingMonth = month;
              }),
            ),
          ),
        );
      },
    ),
  );
}

Future<_StatsDateRange?> _showStatsAllPicker(
  BuildContext context, {
  required DateTime initialStart,
  required DateTime initialEnd,
}) {
  var pendingStart = initialStart;
  var pendingEnd = initialEnd;
  var visibleMonth = DateTime(initialStart.year, initialStart.month);
  var editingStart = true;

  return _showStatsDialog<_StatsDateRange>(
    context,
    StatefulBuilder(
      builder: (context, setDialogState) {
        return _StatsPickerFrame(
          title: '选择全部',
          onConfirm: () => Navigator.of(context).pop(
            _StatsDateRange(start: pendingStart, end: pendingEnd),
          ),
          child: Padding(
            padding: const EdgeInsets.fromLTRB(2, 12, 2, 4),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: _StatsRangeDateRow(
                        label: '开始日期',
                        value: _formatChineseDate(pendingStart),
                        selected: editingStart,
                        onTap: () => setDialogState(() {
                          editingStart = true;
                          visibleMonth = DateTime(
                            pendingStart.year,
                            pendingStart.month,
                          );
                        }),
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: _StatsRangeDateRow(
                        label: '结束日期',
                        value: _formatChineseDate(pendingEnd),
                        selected: !editingStart,
                        onTap: () => setDialogState(() {
                          editingStart = false;
                          visibleMonth = DateTime(
                            pendingEnd.year,
                            pendingEnd.month,
                          );
                        }),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                _StatsMonthHeader(
                  label: _formatChineseMonth(visibleMonth),
                  onTapLabel: () async {
                    final selected = await _showStatsYearMonthPicker(
                      context,
                      initialMonth: visibleMonth,
                    );
                    if (selected == null) return;
                    setDialogState(() => visibleMonth = selected);
                  },
                  onPrevious: () => setDialogState(() {
                    visibleMonth = DateTime(
                      visibleMonth.year,
                      visibleMonth.month - 1,
                    );
                  }),
                  onNext: () => setDialogState(() {
                    visibleMonth = DateTime(
                      visibleMonth.year,
                      visibleMonth.month + 1,
                    );
                  }),
                ),
                const SizedBox(height: 14),
                _StatsSingleDayCalendar(
                  visibleMonth: visibleMonth,
                  selectedStart: pendingStart,
                  selectedEnd: pendingEnd,
                  onSelect: (date) => setDialogState(() {
                    final selectedDay = DateTime(date.year, date.month, date.day);
                    visibleMonth = DateTime(selectedDay.year, selectedDay.month);
                    if (editingStart) {
                      pendingStart = selectedDay;
                      if (pendingStart.isAfter(pendingEnd)) {
                        pendingEnd = selectedDay;
                      }
                      editingStart = false;
                    } else {
                      pendingEnd = selectedDay;
                      if (pendingEnd.isBefore(pendingStart)) {
                        pendingStart = selectedDay;
                      }
                    }
                  }),
                ),
                const SizedBox(height: 18),
                Center(
                  child: Text(
                    '已选择：${_formatChineseDate(pendingStart)} - '
                    '${_formatChineseDate(pendingEnd)}',
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      color: Colors.white.withOpacity(0.62),
                      fontSize: 14,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
              ],
            ),
          ),
        );
      },
    ),
  );
}

const double _statsPickerItemExtent = 58;
const Color _statsWheelBlue = Color(0xFF76B7FF);

class _StatsScrollableMonthList extends StatefulWidget {
  const _StatsScrollableMonthList({
    required this.selectedMonth,
    required this.onSelect,
  });

  final DateTime selectedMonth;
  final ValueChanged<DateTime> onSelect;

  @override
  State<_StatsScrollableMonthList> createState() =>
      _StatsScrollableMonthListState();
}

class _StatsScrollableMonthListState extends State<_StatsScrollableMonthList> {
  late final DateTime _firstMonth;
  late final int _monthCount;
  late final FixedExtentScrollController _controller;

  @override
  void initState() {
    super.initState();
    _firstMonth = DateTime(widget.selectedMonth.year - 8);
    _monthCount = 17 * 12;
    final initialIndex = _monthIndex(widget.selectedMonth);
    _controller = FixedExtentScrollController(initialItem: initialIndex);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  int _monthIndex(DateTime month) {
    return (month.year - _firstMonth.year) * 12 +
        month.month -
        _firstMonth.month;
  }

  DateTime _monthAt(int index) {
    return DateTime(_firstMonth.year, _firstMonth.month + index);
  }

  @override
  Widget build(BuildContext context) {
    return _StatsWheelViewport(
      child: ListWheelScrollView.useDelegate(
        controller: _controller,
        physics: const FixedExtentScrollPhysics(),
        itemExtent: _statsPickerItemExtent,
        diameterRatio: 1.55,
        perspective: 0.0025,
        squeeze: 1.05,
        overAndUnderCenterOpacity: 0.52,
        onSelectedItemChanged: (index) => widget.onSelect(_monthAt(index)),
        childDelegate: ListWheelChildBuilderDelegate(
          childCount: _monthCount,
          builder: (context, index) {
            if (index < 0 || index >= _monthCount) return null;
            final month = _monthAt(index);
            final selected = month.year == widget.selectedMonth.year &&
                month.month == widget.selectedMonth.month;
            return _StatsWheelItem(
              label: _formatChineseMonth(month),
              selected: selected,
              onTap: () {
                _controller.animateToItem(
                  index,
                  duration: const Duration(milliseconds: 220),
                  curve: Curves.easeOutCubic,
                );
                widget.onSelect(month);
              },
            );
          },
        ),
      ),
    );
  }
}

class _StatsScrollableYearList extends StatefulWidget {
  const _StatsScrollableYearList({
    required this.selectedYear,
    required this.onSelect,
  });

  final int selectedYear;
  final ValueChanged<int> onSelect;

  @override
  State<_StatsScrollableYearList> createState() =>
      _StatsScrollableYearListState();
}

class _StatsScrollableYearListState extends State<_StatsScrollableYearList> {
  late final int _firstYear;
  late final int _yearCount;
  late final FixedExtentScrollController _controller;

  @override
  void initState() {
    super.initState();
    _firstYear = widget.selectedYear - 50;
    _yearCount = 101;
    final initialIndex = widget.selectedYear - _firstYear;
    _controller = FixedExtentScrollController(initialItem: initialIndex);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return _StatsWheelViewport(
      child: ListWheelScrollView.useDelegate(
        controller: _controller,
        physics: const FixedExtentScrollPhysics(),
        itemExtent: _statsPickerItemExtent,
        diameterRatio: 1.55,
        perspective: 0.0025,
        squeeze: 1.05,
        overAndUnderCenterOpacity: 0.52,
        onSelectedItemChanged: (index) => widget.onSelect(_firstYear + index),
        childDelegate: ListWheelChildBuilderDelegate(
          childCount: _yearCount,
          builder: (context, index) {
            if (index < 0 || index >= _yearCount) return null;
            final year = _firstYear + index;
            return _StatsWheelItem(
              label: '$year 年',
              selected: year == widget.selectedYear,
              onTap: () {
                _controller.animateToItem(
                  index,
                  duration: const Duration(milliseconds: 220),
                  curve: Curves.easeOutCubic,
                );
                widget.onSelect(year);
              },
            );
          },
        ),
      ),
    );
  }
}

class _StatsYearMonthWheelPicker extends StatefulWidget {
  const _StatsYearMonthWheelPicker({
    required this.selectedYear,
    required this.selectedMonth,
    required this.onYearChanged,
    required this.onMonthChanged,
  });

  final int selectedYear;
  final int selectedMonth;
  final ValueChanged<int> onYearChanged;
  final ValueChanged<int> onMonthChanged;

  @override
  State<_StatsYearMonthWheelPicker> createState() =>
      _StatsYearMonthWheelPickerState();
}

class _StatsYearMonthWheelPickerState extends State<_StatsYearMonthWheelPicker> {
  late final int _firstYear;
  late final int _yearCount;
  late final FixedExtentScrollController _yearController;
  late final FixedExtentScrollController _monthController;

  @override
  void initState() {
    super.initState();
    _firstYear = widget.selectedYear - 50;
    _yearCount = 101;
    _yearController = FixedExtentScrollController(initialItem: 50);
    _monthController = FixedExtentScrollController(
      initialItem: widget.selectedMonth - 1,
    );
  }

  @override
  void dispose() {
    _yearController.dispose();
    _monthController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: _StatsWheelViewport(
            horizontalMargin: 8,
            child: ListWheelScrollView.useDelegate(
              controller: _yearController,
              physics: const FixedExtentScrollPhysics(),
              itemExtent: _statsPickerItemExtent,
              diameterRatio: 1.55,
              perspective: 0.0025,
              squeeze: 1.05,
              overAndUnderCenterOpacity: 0.52,
              onSelectedItemChanged: (index) {
                widget.onYearChanged(_firstYear + index);
              },
              childDelegate: ListWheelChildBuilderDelegate(
                childCount: _yearCount,
                builder: (context, index) {
                  if (index < 0 || index >= _yearCount) return null;
                  final year = _firstYear + index;
                  return _StatsWheelItem(
                    label: '$year 年',
                    selected: year == widget.selectedYear,
                    onTap: () {
                      _yearController.animateToItem(
                        index,
                        duration: const Duration(milliseconds: 220),
                        curve: Curves.easeOutCubic,
                      );
                      widget.onYearChanged(year);
                    },
                  );
                },
              ),
            ),
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: _StatsWheelViewport(
            horizontalMargin: 8,
            child: ListWheelScrollView.useDelegate(
              controller: _monthController,
              physics: const FixedExtentScrollPhysics(),
              itemExtent: _statsPickerItemExtent,
              diameterRatio: 1.55,
              perspective: 0.0025,
              squeeze: 1.05,
              overAndUnderCenterOpacity: 0.52,
              onSelectedItemChanged: (index) {
                widget.onMonthChanged(index + 1);
              },
              childDelegate: ListWheelChildBuilderDelegate(
                childCount: 12,
                builder: (context, index) {
                  if (index < 0 || index >= 12) return null;
                  final month = index + 1;
                  return _StatsWheelItem(
                    label: '$month 月',
                    selected: month == widget.selectedMonth,
                    onTap: () {
                      _monthController.animateToItem(
                        index,
                        duration: const Duration(milliseconds: 220),
                        curve: Curves.easeOutCubic,
                      );
                      widget.onMonthChanged(month);
                    },
                  );
                },
              ),
            ),
          ),
        ),
      ],
    );
  }
}

class _StatsWheelViewport extends StatelessWidget {
  const _StatsWheelViewport({
    required this.child,
    this.horizontalMargin = 18,
  });

  final Widget child;
  final double horizontalMargin;

  @override
  Widget build(BuildContext context) {
    return Stack(
      alignment: Alignment.center,
      children: [
        Positioned.fill(child: child),
        IgnorePointer(
          child: Center(
            child: Container(
              height: _statsPickerItemExtent,
              margin: EdgeInsets.symmetric(horizontal: horizontalMargin),
              decoration: BoxDecoration(
                color: _statsWheelBlue.withOpacity(0.10),
                borderRadius: BorderRadius.circular(16),
                border: Border.symmetric(
                  horizontal: BorderSide(
                    color: _statsWheelBlue.withOpacity(0.76),
                    width: 1.2,
                  ),
                ),
              ),
            ),
          ),
        ),
        Positioned(
          top: 0,
          left: 0,
          right: 0,
          height: 56,
          child: IgnorePointer(
            child: DecoratedBox(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                  colors: [
                    const Color(0xFF1F2731),
                    const Color(0xFF1F2731).withOpacity(0),
                  ],
                ),
              ),
            ),
          ),
        ),
        Positioned(
          left: 0,
          right: 0,
          bottom: 0,
          height: 56,
          child: IgnorePointer(
            child: DecoratedBox(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.bottomCenter,
                  end: Alignment.topCenter,
                  colors: [
                    const Color(0xFF171F29),
                    const Color(0xFF171F29).withOpacity(0),
                  ],
                ),
              ),
            ),
          ),
        ),
      ],
    );
  }
}

class _StatsWheelItem extends StatelessWidget {
  const _StatsWheelItem({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      borderRadius: BorderRadius.circular(16),
      onTap: onTap,
      child: Center(
        child: AnimatedDefaultTextStyle(
          duration: const Duration(milliseconds: 120),
          curve: Curves.easeOutCubic,
          style: TextStyle(
            color: Colors.white.withOpacity(selected ? 0.98 : 0.46),
            fontSize: selected ? 25 : 18,
            fontWeight: selected ? FontWeight.w900 : FontWeight.w700,
          ),
          child: Text(
            label,
            maxLines: 1,
            softWrap: false,
          ),
        ),
      ),
    );
  }
}

class _StatsSingleDayCalendar extends StatelessWidget {
  const _StatsSingleDayCalendar({
    required this.visibleMonth,
    required this.selectedStart,
    required this.selectedEnd,
    required this.onSelect,
  });

  final DateTime visibleMonth;
  final DateTime selectedStart;
  final DateTime selectedEnd;
  final ValueChanged<DateTime> onSelect;

  @override
  Widget build(BuildContext context) {
    const weekdays = ['日', '一', '二', '三', '四', '五', '六'];
    final weeks = _calendarWeeksForMonth(visibleMonth);
    return Column(
      children: [
        Row(
          children: [
            for (final weekday in weekdays)
              Expanded(
                child: Center(
                  child: Text(
                    weekday,
                    style: TextStyle(
                      color: Colors.white.withOpacity(0.76),
                      fontSize: 15,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ),
              ),
          ],
        ),
        const SizedBox(height: 12),
        for (final week in weeks)
          SizedBox(
            height: 42,
            child: Row(
              children: [
                for (final day in week)
                  _StatsRangeDayCell(
                    day: day,
                    visibleMonth: visibleMonth,
                    selectedStart: selectedStart,
                    selectedEnd: selectedEnd,
                    onSelect: onSelect,
                  ),
              ],
            ),
          ),
      ],
    );
  }
}

class _StatsRangeDayCell extends StatelessWidget {
  const _StatsRangeDayCell({
    required this.day,
    required this.visibleMonth,
    required this.selectedStart,
    required this.selectedEnd,
    required this.onSelect,
  });

  final DateTime day;
  final DateTime visibleMonth;
  final DateTime selectedStart;
  final DateTime selectedEnd;
  final ValueChanged<DateTime> onSelect;

  @override
  Widget build(BuildContext context) {
    final inMonth = day.month == visibleMonth.month;
    final isStart = _isSameDate(day, selectedStart);
    final isEnd = _isSameDate(day, selectedEnd);
    final inRange = !day.isBefore(selectedStart) && !day.isAfter(selectedEnd);
    final selected = isStart || isEnd;

    return Expanded(
      child: InkWell(
        customBorder: const CircleBorder(),
        onTap: () => onSelect(day),
        child: SizedBox(
          height: 42,
          child: Stack(
            alignment: Alignment.center,
            children: [
              if (inRange)
                Positioned.fill(
                  left: isStart ? 12 : 0,
                  right: isEnd ? 12 : 0,
                  top: 7,
                  bottom: 7,
                  child: DecoratedBox(
                    decoration: BoxDecoration(
                      color: _RideColors.orange.withOpacity(0.16),
                      borderRadius: BorderRadius.horizontal(
                        left: Radius.circular(isStart ? 14 : 0),
                        right: Radius.circular(isEnd ? 14 : 0),
                      ),
                    ),
                  ),
                ),
              Container(
                width: selected ? 30 : 28,
                height: selected ? 30 : 28,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: selected ? _RideColors.orange : Colors.transparent,
                  shape: BoxShape.circle,
                ),
                child: Text(
                  day.day.toString(),
                  style: TextStyle(
                    color: selected
                        ? Colors.black.withOpacity(0.86)
                        : inRange
                            ? Colors.white.withOpacity(0.92)
                            : Colors.white.withOpacity(inMonth ? 0.76 : 0.42),
                    fontSize: 14,
                    fontWeight: selected || inRange
                        ? FontWeight.w900
                        : FontWeight.w700,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _StatsPickerFrame extends StatelessWidget {
  const _StatsPickerFrame({
    required this.title,
    required this.child,
    required this.onConfirm,
  });

  final String title;
  final Widget child;
  final VoidCallback onConfirm;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: Colors.white.withOpacity(0.08)),
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            const Color(0xFF252D38).withOpacity(0.98),
            const Color(0xFF151C26).withOpacity(0.99),
          ],
        ),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.48),
            blurRadius: 36,
            offset: const Offset(0, 22),
          ),
        ],
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            SizedBox(
              height: 74,
              child: Stack(
                alignment: Alignment.center,
                children: [
                  Align(
                    alignment: Alignment.centerLeft,
                    child: IconButton(
                      onPressed: () => Navigator.of(context).pop(),
                      icon: const Icon(Icons.close, color: Colors.white, size: 30),
                    ),
                  ),
                  Text(
                    title,
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 21,
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                  Align(
                    alignment: Alignment.centerRight,
                    child: TextButton(
                      onPressed: onConfirm,
                      child: const Text(
                        '确定',
                        style: TextStyle(
                          color: _RideColors.orange,
                          fontSize: 18,
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
            Divider(height: 1, color: Colors.white.withOpacity(0.07)),
            Padding(
              padding: const EdgeInsets.fromLTRB(22, 18, 22, 24),
              child: child,
            ),
          ],
        ),
      ),
    );
  }
}

class _StatsMonthHeader extends StatelessWidget {
  const _StatsMonthHeader({
    required this.label,
    required this.onPrevious,
    required this.onNext,
    this.onTapLabel,
  });

  final String label;
  final VoidCallback onPrevious;
  final VoidCallback onNext;
  final VoidCallback? onTapLabel;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        IconButton(
          onPressed: onPrevious,
          icon: const Icon(Icons.chevron_left, color: Colors.white, size: 28),
        ),
        InkWell(
          borderRadius: BorderRadius.circular(14),
          onTap: onTapLabel,
          child: SizedBox(
            width: 188,
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Flexible(
                  child: FittedBox(
                    fit: BoxFit.scaleDown,
                    child: Text(
                      label,
                      textAlign: TextAlign.center,
                      maxLines: 1,
                      softWrap: false,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 19,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                  ),
                ),
                if (onTapLabel != null) ...[
                  const SizedBox(width: 4),
                  Icon(
                    Icons.expand_more,
                    color: Colors.white.withOpacity(0.62),
                    size: 20,
                  ),
                ],
              ],
            ),
          ),
        ),
        IconButton(
          onPressed: onNext,
          icon: const Icon(Icons.chevron_right, color: Colors.white, size: 28),
        ),
      ],
    );
  }
}

class _StatsWeekCalendar extends StatelessWidget {
  const _StatsWeekCalendar({
    required this.visibleMonth,
    required this.selectedWeekStart,
    required this.onSelect,
  });

  final DateTime visibleMonth;
  final DateTime selectedWeekStart;
  final ValueChanged<DateTime> onSelect;

  @override
  Widget build(BuildContext context) {
    const weekdays = ['日', '一', '二', '三', '四', '五', '六'];
    final weeks = _calendarWeeksForMonth(visibleMonth);
    return Column(
      children: [
        Row(
          children: [
            for (final weekday in weekdays)
              Expanded(
                child: Center(
                  child: Text(
                    weekday,
                    style: TextStyle(
                      color: Colors.white.withOpacity(0.76),
                      fontSize: 15,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ),
              ),
          ],
        ),
        const SizedBox(height: 12),
        for (final week in weeks)
          _StatsWeekCalendarRow(
            days: week,
            visibleMonth: visibleMonth,
            selectedWeekStart: selectedWeekStart,
            onSelect: onSelect,
          ),
      ],
    );
  }
}

class _StatsWeekCalendarRow extends StatelessWidget {
  const _StatsWeekCalendarRow({
    required this.days,
    required this.visibleMonth,
    required this.selectedWeekStart,
    required this.onSelect,
  });

  final List<DateTime> days;
  final DateTime visibleMonth;
  final DateTime selectedWeekStart;
  final ValueChanged<DateTime> onSelect;

  @override
  Widget build(BuildContext context) {
    final isSelectedRow = days.any(
      (day) => _isSameDate(_weekStartSunday(day), selectedWeekStart),
    );
    return SizedBox(
      height: 42,
      child: Stack(
        alignment: Alignment.center,
        children: [
          if (isSelectedRow)
            Positioned.fill(
              left: 3,
              right: 3,
              top: 4,
              bottom: 4,
              child: DecoratedBox(
                decoration: BoxDecoration(
                  color: _RideColors.orange.withOpacity(0.20),
                  borderRadius: BorderRadius.circular(22),
                  border: Border.all(
                    color: _RideColors.orange.withOpacity(0.72),
                  ),
                ),
              ),
            ),
          Row(
            children: [
              for (final day in days)
                Expanded(
                  child: InkWell(
                    customBorder: const CircleBorder(),
                    onTap: () => onSelect(day),
                    child: Center(
                      child: _StatsDayCircle(
                        day: day,
                        visibleMonth: visibleMonth,
                        selected: _isSameDate(
                          _weekStartSunday(day),
                          selectedWeekStart,
                        ),
                      ),
                    ),
                  ),
                ),
            ],
          ),
        ],
      ),
    );
  }
}

class _StatsDayCircle extends StatelessWidget {
  const _StatsDayCircle({
    required this.day,
    required this.visibleMonth,
    required this.selected,
  });

  final DateTime day;
  final DateTime visibleMonth;
  final bool selected;

  @override
  Widget build(BuildContext context) {
    final inMonth = day.month == visibleMonth.month;
    return Container(
      width: selected ? 30 : 28,
      height: selected ? 30 : 28,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: selected ? _RideColors.orange : Colors.transparent,
        shape: BoxShape.circle,
      ),
      child: Text(
        day.day.toString(),
        style: TextStyle(
          color: selected
              ? Colors.black.withOpacity(0.86)
              : Colors.white.withOpacity(inMonth ? 0.76 : 0.42),
          fontSize: 14,
          fontWeight: selected ? FontWeight.w900 : FontWeight.w700,
        ),
      ),
    );
  }
}

class _StatsPickerListItem extends StatelessWidget {
  const _StatsPickerListItem({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      borderRadius: BorderRadius.circular(16),
      onTap: onTap,
      child: Container(
        height: 52,
        width: double.infinity,
        alignment: Alignment.center,
        margin: const EdgeInsets.symmetric(vertical: 3),
        decoration: BoxDecoration(
          color: selected ? Colors.white.withOpacity(0.08) : Colors.transparent,
          borderRadius: BorderRadius.circular(16),
        ),
        child: Text(
          label,
          style: TextStyle(
            color: Colors.white.withOpacity(selected ? 0.96 : 0.34),
            fontSize: selected ? 25 : 18,
            fontWeight: selected ? FontWeight.w900 : FontWeight.w700,
          ),
        ),
      ),
    );
  }
}

class _StatsRangeDateRow extends StatelessWidget {
  const _StatsRangeDateRow({
    required this.label,
    required this.value,
    required this.onTap,
    this.selected = false,
  });

  final String label;
  final String value;
  final VoidCallback onTap;
  final bool selected;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: TextStyle(
            color: Colors.white.withOpacity(0.58),
            fontSize: 15,
            fontWeight: FontWeight.w800,
          ),
        ),
        const SizedBox(height: 12),
        InkWell(
          borderRadius: BorderRadius.circular(15),
          onTap: onTap,
          child: Container(
            height: 54,
            padding: const EdgeInsets.symmetric(horizontal: 12),
            decoration: BoxDecoration(
              color: selected
                  ? _RideColors.orange.withOpacity(0.14)
                  : Colors.white.withOpacity(0.06),
              borderRadius: BorderRadius.circular(15),
              border: Border.all(
                color: selected
                    ? _RideColors.orange.withOpacity(0.78)
                    : Colors.white.withOpacity(0.07),
              ),
            ),
            child: Row(
              children: [
                Expanded(
                  child: FittedBox(
                    fit: BoxFit.scaleDown,
                    alignment: Alignment.centerLeft,
                    child: Text(
                      value,
                      maxLines: 1,
                      softWrap: false,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 18,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                  ),
                ),
                Icon(
                  selected ? Icons.edit_calendar : Icons.calendar_month,
                  color: selected
                      ? _RideColors.orange
                      : Colors.white.withOpacity(0.36),
                  size: 21,
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

DateTime _weekStartSunday(DateTime date) {
  final day = DateTime(date.year, date.month, date.day);
  return day.subtract(Duration(days: day.weekday % 7));
}

List<List<DateTime>> _calendarWeeksForMonth(DateTime month) {
  final firstDay = DateTime(month.year, month.month);
  final lastDay = DateTime(month.year, month.month + 1, 0);
  final start = _weekStartSunday(firstDay);
  final end = _weekStartSunday(lastDay).add(const Duration(days: 6));
  final weeks = <List<DateTime>>[];
  var cursor = start;
  while (!cursor.isAfter(end)) {
    weeks.add([for (var i = 0; i < 7; i++) cursor.add(Duration(days: i))]);
    cursor = cursor.add(const Duration(days: 7));
  }
  return weeks;
}

bool _isSameDate(DateTime a, DateTime b) {
  return a.year == b.year && a.month == b.month && a.day == b.day;
}

String _formatSlashDate(DateTime date) {
  return '${date.year}/${date.month.toString().padLeft(2, '0')}/'
      '${date.day.toString().padLeft(2, '0')}';
}

String _formatChineseDate(DateTime date) {
  return '${date.year}年${date.month}月${date.day}日';
}

String _formatChineseMonth(DateTime date) {
  return '${date.year}年${date.month}月';
}

String _formatChineseMonthDay(DateTime date) {
  return '${date.month}月${date.day}日';
}

String _formatMonthDayTick(DateTime date) {
  return '${date.month.toString().padLeft(2, '0')}/'
      '${date.day.toString().padLeft(2, '0')}';
}

String _weekdayLabel(DateTime date) {
  switch (date.weekday) {
    case DateTime.monday:
      return '周一';
    case DateTime.tuesday:
      return '周二';
    case DateTime.wednesday:
      return '周三';
    case DateTime.thursday:
      return '周四';
    case DateTime.friday:
      return '周五';
    case DateTime.saturday:
      return '周六';
    case DateTime.sunday:
    default:
      return '周日';
  }
}

List<DateTime> _datesForMonth(DateTime month) {
  final normalized = DateTime(month.year, month.month);
  final daysInMonth = DateTime(normalized.year, normalized.month + 1, 0).day;
  return [
    for (var day = 1; day <= daysInMonth; day++)
      DateTime(normalized.year, normalized.month, day),
  ];
}

List<int> _monthTickIndices(int dayCount) {
  final indices = <int>[];
  for (final candidate in <int>[0, 7, 14, 21, dayCount - 1]) {
    if (candidate < 0 || candidate >= dayCount || indices.contains(candidate)) {
      continue;
    }
    indices.add(candidate);
  }
  return indices;
}

DateTime _dateOnly(DateTime date) {
  return DateTime(date.year, date.month, date.day);
}

DateTime _exclusiveDayAfter(DateTime date) {
  final day = _dateOnly(date);
  return DateTime(day.year, day.month, day.day + 1);
}

List<RideSession> _ridesInRange(
  List<RideSession> rides,
  DateTime startInclusive,
  DateTime endExclusive,
) {
  return rides
      .where(
        (ride) =>
            !ride.startTime.isBefore(startInclusive) &&
            ride.startTime.isBefore(endExclusive),
      )
      .toList(growable: false);
}

List<double> _dailyDistanceSeries(
  List<RideSession> rides,
  List<DateTime> dates,
) {
  return [
    for (final date in dates)
      _sumDistance(_ridesInRange(rides, _dateOnly(date), _exclusiveDayAfter(date))),
  ];
}

List<double> _dailyDurationSeries(
  List<RideSession> rides,
  List<DateTime> dates,
) {
  return [
    for (final date in dates)
      _sumDurationHours(
        _ridesInRange(rides, _dateOnly(date), _exclusiveDayAfter(date)),
      ),
  ];
}

List<double> _monthlyDistanceSeries(List<RideSession> rides) {
  final values = List<double>.filled(12, 0);
  for (final ride in rides) {
    values[ride.startTime.month - 1] += ride.distanceKm;
  }
  return values;
}

List<double> _monthlyDurationSeries(List<RideSession> rides) {
  final values = List<double>.filled(12, 0);
  for (final ride in rides) {
    values[ride.startTime.month - 1] += ride.durationSeconds / 3600;
  }
  return values;
}

List<int> _yearsForRange(DateTime start, DateTime end) {
  final firstYear = math.min(start.year, end.year);
  final lastYear = math.max(start.year, end.year);
  return [for (var year = firstYear; year <= lastYear; year++) year];
}

List<double> _yearlyDistanceSeries(List<RideSession> rides, List<int> years) {
  return [
    for (final year in years)
      _sumDistance(
        rides.where((ride) => ride.startTime.year == year),
      ),
  ];
}

List<double> _yearlyDurationSeries(List<RideSession> rides, List<int> years) {
  return [
    for (final year in years)
      _sumDurationHours(
        rides.where((ride) => ride.startTime.year == year),
      ),
  ];
}

double _sumDistance(Iterable<RideSession> rides) {
  return rides.fold<double>(0, (sum, ride) => sum + ride.distanceKm);
}

double _sumDurationHours(Iterable<RideSession> rides) {
  return rides.fold<double>(
    0,
    (sum, ride) => sum + ride.durationSeconds / 3600,
  );
}

double _barMaxValue(List<double> values, {required double fallback}) {
  if (values.isEmpty) return fallback;
  final maxValue = values.fold<double>(
    0,
    (currentMax, value) => math.max(currentMax, value).toDouble(),
  );
  if (maxValue <= 0) return fallback;
  return math.max(fallback, maxValue * 1.25);
}

class _StatsOverview extends StatelessWidget {
  const _StatsOverview({required this.stats});

  final _RideStats stats;

  @override
  Widget build(BuildContext context) {
    return _GlassPanel(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            '总览',
            style: TextStyle(
              color: Colors.white,
              fontSize: 20,
              fontWeight: FontWeight.w900,
            ),
          ),
          const SizedBox(height: 18),
          LayoutBuilder(
            builder: (context, constraints) {
              final columns = constraints.maxWidth < 360 ? 2 : 3;
              return GridView.count(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                crossAxisCount: columns,
                childAspectRatio: columns == 2 ? 1.72 : 1.34,
                mainAxisSpacing: 12,
                crossAxisSpacing: 10,
                children: [
                  _OverviewMetric(
                    label: '活动次数',
                    value: stats.rideCount,
                    unit: '次',
                  ),
                  _OverviewMetric(
                    label: '总里程',
                    value: stats.totalDistance,
                    unit: 'km',
                  ),
                  _OverviewMetric(
                    label: '总时间',
                    value: stats.totalDuration,
                    unit: '',
                  ),
                  _OverviewMetric(
                    label: '总爬升',
                    value: stats.totalClimb,
                    unit: 'm',
                  ),
                  _OverviewMetric(
                    label: '总消耗',
                    value: stats.calories,
                    unit: 'kcal',
                  ),
                  _OverviewMetric(
                    label: '平均速度',
                    value: stats.avgSpeed,
                    unit: 'km/h',
                  ),
                ],
              );
            },
          ),
        ],
      ),
    );
  }
}

class _OverviewMetric extends StatelessWidget {
  const _OverviewMetric({
    required this.label,
    required this.value,
    required this.unit,
  });

  final String label;
  final String value;
  final String unit;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        border: Border(
          right: BorderSide(color: Colors.white.withOpacity(0.08)),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(
              color: Colors.white.withOpacity(0.56),
              fontSize: 13,
              fontWeight: FontWeight.w700,
            ),
          ),
          const Spacer(),
          FittedBox(
            fit: BoxFit.scaleDown,
            alignment: Alignment.centerLeft,
            child: RichText(
              maxLines: 1,
              text: TextSpan(
                children: [
                  TextSpan(
                    text: value,
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 22,
                      height: 1,
                      fontWeight: FontWeight.w900,
                      letterSpacing: -0.6,
                    ),
                  ),
                  if (unit.isNotEmpty)
                    TextSpan(
                      text: ' $unit',
                      style: TextStyle(
                        color: Colors.white.withOpacity(0.58),
                        fontSize: 12,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _BarTrendPanel extends StatefulWidget {
  const _BarTrendPanel({
    required this.title,
    required this.unit,
    required this.values,
    required this.labels,
    required this.color,
    required this.tooltipTitle,
    required this.tooltipValue,
    required this.maxValue,
    this.labelIndices,
    this.tooltipTitles,
  })  : assert(labelIndices == null || labelIndices.length == labels.length),
        assert(tooltipTitles == null || tooltipTitles.length == values.length);

  final String title;
  final String unit;
  final List<double> values;
  final List<String> labels;
  final List<int>? labelIndices;
  final Color color;
  final List<String>? tooltipTitles;
  final String tooltipTitle;
  final String tooltipValue;
  final double maxValue;

  @override
  State<_BarTrendPanel> createState() => _BarTrendPanelState();
}

class _BarTrendPanelState extends State<_BarTrendPanel> {
  Timer? _hideTimer;
  int? _tooltipIndex;

  int? get _validTooltipIndex {
    final index = _tooltipIndex;
    if (index == null || index < 0 || index >= widget.values.length) {
      return null;
    }
    return index;
  }

  @override
  void dispose() {
    _hideTimer?.cancel();
    super.dispose();
  }

  void _showTooltip(int index) {
    if (index < 0 || index >= widget.values.length) return;
    _hideTimer?.cancel();
    setState(() => _tooltipIndex = index);
    _hideTimer = Timer(const Duration(seconds: 3), () {
      if (mounted) setState(() => _tooltipIndex = null);
    });
  }

  int? _indexForTap(Offset local, Size size) {
    if (widget.values.isEmpty || size.width <= 54 || size.height <= 52) {
      return null;
    }
    final chartRect = Rect.fromLTWH(34, 26, size.width - 54, size.height - 52);
    if (!chartRect.inflate(18).contains(local)) return null;
    final raw =
        ((local.dx - chartRect.left) / chartRect.width * widget.values.length)
            .floor();
    if (raw < 0) return 0;
    if (raw >= widget.values.length) return widget.values.length - 1;
    return raw;
  }

  String _tooltipTitleFor(int index) {
    final titles = widget.tooltipTitles;
    if (titles != null && index >= 0 && index < titles.length) {
      return titles[index];
    }
    return widget.tooltipTitle;
  }

  String _tooltipValueFor(int index) {
    if (index < 0 || index >= widget.values.length) return widget.tooltipValue;
    final value = widget.values[index];
    if (widget.unit.contains('小时')) {
      return value >= 1
          ? '${value.toStringAsFixed(1)} 小时'
          : '${(value * 60).round()} 分钟';
    }
    return '${value.toStringAsFixed(1)} km';
  }

  @override
  Widget build(BuildContext context) {
    return _GlassPanel(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 14),
      child: Column(
        children: [
          Row(
            children: [
              Text(
                widget.title,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 20,
                  fontWeight: FontWeight.w900,
                ),
              ),
              const Spacer(),
              Text(
                widget.unit,
                style: TextStyle(
                  color: Colors.white.withOpacity(0.54),
                  fontSize: 13,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          SizedBox(
            height: 126,
            child: LayoutBuilder(
              builder: (context, constraints) {
                final size = Size(constraints.maxWidth, constraints.maxHeight);
                final selectedIndex = _validTooltipIndex;
                return TapRegion(
                  onTapOutside: (_) {
                    if (_tooltipIndex != null) {
                      _hideTimer?.cancel();
                      setState(() => _tooltipIndex = null);
                    }
                  },
                  child: GestureDetector(
                    behavior: HitTestBehavior.opaque,
                    onTapDown: (details) {
                      final index = _indexForTap(details.localPosition, size);
                      if (index != null) _showTooltip(index);
                    },
                    child: CustomPaint(
                      painter: _BarChartPainter(
                        values: widget.values,
                        labels: widget.labels,
                        labelIndices: widget.labelIndices,
                        color: widget.color,
                        maxValue: widget.maxValue,
                        tooltipIndex: selectedIndex,
                        tooltipTitle: selectedIndex == null
                            ? widget.tooltipTitle
                            : _tooltipTitleFor(selectedIndex),
                        tooltipValue: selectedIndex == null
                            ? widget.tooltipValue
                            : _tooltipValueFor(selectedIndex),
                      ),
                      child: const SizedBox.expand(),
                    ),
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}
class _AnnualDistributionPanel extends StatelessWidget {
  const _AnnualDistributionPanel({required this.outdoorDistanceKm});

  final double outdoorDistanceKm;

  @override
  Widget build(BuildContext context) {
    const colors = [
      _RideColors.orange,
      Color(0xFF268DFF),
      Color(0xFF62D729),
    ];
    final hasDistance = outdoorDistanceKm > 0;
    const distribution = <double>[1, 0, 0];
    const labels = ['户外骑行', '室内骑行', '其他运动'];
    final outdoorDistanceText = outdoorDistanceKm.toStringAsFixed(1);
    final details = [
      '$outdoorDistanceText km  ${hasDistance ? '100%' : '0%'}',
      '0.0 km  0%',
      '0.0 km  0%',
    ];

    return _GlassPanel(
      padding: const EdgeInsets.all(16),
      child: Column(
        children: [
          Row(
            children: [
              const Text(
                '运动类型分布',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 20,
                  fontWeight: FontWeight.w900,
                ),
              ),
              const Spacer(),
              Text(
                '单位：km',
                style: TextStyle(
                  color: Colors.white.withOpacity(0.54),
                  fontSize: 13,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ),
          const SizedBox(height: 18),
          LayoutBuilder(
            builder: (context, constraints) {
              final compact = constraints.maxWidth < 400;
              final legend = Column(
                children: [
                  _DistributionRow(
                    color: _RideColors.orange,
                    label: '户外骑行',
                    value: '$outdoorDistanceText km',
                    ratio: hasDistance ? '100%' : '0%',
                  ),
                  const SizedBox(height: 18),
                  const _DistributionRow(
                    color: Color(0xFF268DFF),
                    label: '室内骑行',
                    value: '0.0 km',
                    ratio: '0%',
                  ),
                  const SizedBox(height: 18),
                  const _DistributionRow(
                    color: Color(0xFF62D729),
                    label: '其他运动',
                    value: '0.0 km',
                    ratio: '0%',
                  ),
                ],
              );
              final donut = _InteractiveDonutChart(
                size: compact ? 136 : 148,
                strokeWidth: 25,
                colors: colors,
                values: distribution,
                labels: labels,
                details: details,
                backgroundColor: _RideColors.panel,
                center: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Text(
                      '1026.3',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 24,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                    Text(
                      '总里程 (km)',
                      style: TextStyle(
                        color: Colors.white.withOpacity(0.54),
                        fontSize: 12,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ],
                ),
              );

              if (compact) {
                return Column(
                  children: [
                    legend,
                    const SizedBox(height: 16),
                    donut,
                  ],
                );
              }
              return Row(
                children: [
                  Expanded(child: legend),
                  const SizedBox(width: 20),
                  donut,
                ],
              );
            },
          ),
        ],
      ),
    );
  }
}

class _DistributionRow extends StatelessWidget {
  const _DistributionRow({
    required this.color,
    required this.label,
    required this.value,
    required this.ratio,
  });

  final Color color;
  final String label;
  final String value;
  final String ratio;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 14,
          height: 14,
          decoration: BoxDecoration(color: color, shape: BoxShape.circle),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Text(
            label,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 16,
              fontWeight: FontWeight.w800,
            ),
          ),
        ),
        Text(
          value,
          style: TextStyle(
            color: Colors.white.withOpacity(0.82),
            fontSize: 14,
            fontWeight: FontWeight.w800,
          ),
        ),
        const SizedBox(width: 12),
        Text(
          ratio,
          style: TextStyle(
            color: Colors.white.withOpacity(0.82),
            fontSize: 14,
            fontWeight: FontWeight.w800,
          ),
        ),
      ],
    );
  }
}

class _InteractiveDonutChart extends StatefulWidget {
  const _InteractiveDonutChart({
    required this.size,
    required this.colors,
    required this.values,
    required this.labels,
    required this.details,
    required this.backgroundColor,
    required this.center,
    this.strokeWidth = 16,
  });

  final double size;
  final List<Color> colors;
  final List<double> values;
  final List<String> labels;
  final List<String> details;
  final Color backgroundColor;
  final Widget center;
  final double strokeWidth;

  @override
  State<_InteractiveDonutChart> createState() => _InteractiveDonutChartState();
}

class _InteractiveDonutChartState extends State<_InteractiveDonutChart> {
  Timer? _hideTimer;
  int? _selectedIndex;

  @override
  void dispose() {
    _hideTimer?.cancel();
    super.dispose();
  }

  void _handleTap(TapDownDetails details) {
    final index = _segmentForTap(details.localPosition);
    if (index == null) return;
    _hideTimer?.cancel();
    setState(() => _selectedIndex = index);
    _hideTimer = Timer(const Duration(seconds: 3), () {
      if (mounted) setState(() => _selectedIndex = null);
    });
  }

  int? _segmentForTap(Offset local) {
    if (widget.values.isEmpty) return null;
    final center = Offset(widget.size / 2, widget.size / 2);
    final delta = local - center;
    final distance = delta.distance;
    final radius = widget.size * 0.38;
    if (distance > radius + widget.strokeWidth) return null;

    var angle = math.atan2(delta.dy, delta.dx) + math.pi / 2;
    while (angle < 0) {
      angle += math.pi * 2;
    }
    while (angle >= math.pi * 2) {
      angle -= math.pi * 2;
    }

    final total = widget.values.fold<double>(0, (sum, value) => sum + value);
    if (total <= 0) return null;
    final target = angle / (math.pi * 2) * total;
    var cursor = 0.0;
    for (var i = 0; i < widget.values.length; i++) {
      cursor += widget.values[i];
      if (target <= cursor) return i;
    }
    return widget.values.length - 1;
  }

  @override
  Widget build(BuildContext context) {
    final selected = _selectedIndex;
    final tooltip = selected == null
        ? null
        : '${widget.labels[selected]}\n${widget.details[selected]}';

    return TapRegion(
      onTapOutside: (_) {
        if (_selectedIndex != null) {
          _hideTimer?.cancel();
          setState(() => _selectedIndex = null);
        }
      },
      child: SizedBox(
        width: widget.size,
        height: widget.size,
        child: GestureDetector(
          behavior: HitTestBehavior.opaque,
          onTapDown: _handleTap,
          child: Stack(
            clipBehavior: Clip.none,
            alignment: Alignment.center,
            children: [
              CustomPaint(
                painter: _DonutPainter(
                  colors: widget.colors,
                  values: widget.values,
                  backgroundColor: widget.backgroundColor,
                  strokeWidth: widget.strokeWidth,
                  selectedIndex: selected,
                ),
                child: const SizedBox.expand(),
              ),
              widget.center,
              Positioned(
                top: -8,
                left: -24,
                right: -24,
                child: IgnorePointer(
                  child: AnimatedOpacity(
                    duration: const Duration(milliseconds: 160),
                    opacity: tooltip == null ? 0 : 1,
                    child: Center(
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 10,
                          vertical: 7,
                        ),
                        decoration: BoxDecoration(
                          color: const Color(0xFF303744).withOpacity(0.96),
                          borderRadius: BorderRadius.circular(10),
                          border: Border.all(color: Colors.white.withOpacity(0.08)),
                        ),
                        child: Text(
                          tooltip ?? '',
                          textAlign: TextAlign.center,
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 11,
                            height: 1.25,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _RoutesPage extends StatefulWidget {
  const _RoutesPage({required this.controller});

  final RideController controller;

  @override
  State<_RoutesPage> createState() => _RoutesPageState();
}

const _routeFilterLabels = <String>['全部', '简单', '中等', '困难'];

class _RoutesPageState extends State<_RoutesPage> {
  static const _favoriteRoutesPrefsKey = 'speedometer.favorite_routes';
  static const _importedRoutesPrefsKey = 'speedometer.imported_routes';
  static const _selectedRoutePrefsKey = 'speedometer.selected_route';
  static const _routeModeCount = 3;

  late final PageController _routePageController;
  var _modeIndex = 0;
  var _routeFilterIndex = 0;
  var _routeFabExpanded = false;
  var _importingRoute = false;
  final _favoriteRouteTitles = <String>{};
  final _importedRoutes = <_RouteListEntry>[];

  List<_RouteListEntry> get _allRoutes => _importedRoutes;

  String get _routeFilterLabel => _routeFilterLabels[_routeFilterIndex];

  List<_RouteListEntry> _routesForMode(int index) {
    final routes = _allRoutes;
    final modeRoutes = switch (index) {
      1 => routes
          .where((route) => _favoriteRouteTitles.contains(route.title))
          .toList(),
      2 => _importedRoutes,
      _ => routes,
    };
    if (_routeFilterIndex == 0) return modeRoutes;
    final difficulty = _routeFilterLabel;
    return modeRoutes
        .where((route) => route.difficulty == difficulty)
        .toList(growable: false);
  }

  void _selectRouteMode(int index) {
    if (index < 0 || index >= _routeModeCount) return;
    if (index == _modeIndex) return;
    setState(() => _modeIndex = index);
    if (!_routePageController.hasClients) return;
    unawaited(
      _routePageController.animateToPage(
        index,
        duration: const Duration(milliseconds: 220),
        curve: Curves.easeOutCubic,
      ),
    );
  }

  void _handleRouteModePageChanged(int index) {
    if (index == _modeIndex) return;
    setState(() => _modeIndex = index);
  }

  void _selectRouteFilter(int index) {
    if (index < 0 || index >= _routeFilterLabels.length) return;
    if (index == _routeFilterIndex) return;
    setState(() => _routeFilterIndex = index);
  }

  void _openRouteFilterSheet() {
    unawaited(
      _showRouteFilterActions(
        context,
        selectedIndex: _routeFilterIndex,
        onSelect: _selectRouteFilter,
      ),
    );
  }

  @override
  void initState() {
    super.initState();
    _routePageController = PageController(initialPage: _modeIndex);
    unawaited(_loadRouteState());
  }

  @override
  void dispose() {
    _routePageController.dispose();
    super.dispose();
  }

  Future<void> _loadRouteState() async {
    final prefs = await SharedPreferences.getInstance();
    final importedRoutes = prefs
            .getStringList(_importedRoutesPrefsKey)
            ?.map(_RouteListEntry.tryFromJson)
            .whereType<_RouteListEntry>()
            .toList() ??
        <_RouteListEntry>[];
    final knownTitles = importedRoutes.map((route) => route.title).toSet();
    final titles = prefs
            .getStringList(_favoriteRoutesPrefsKey)
            ?.where(knownTitles.contains)
            .toSet() ??
        <String>{};
    final selectedTitle = prefs.getString(_selectedRoutePrefsKey);
    _RouteListEntry? selectedRoute;
    if (selectedTitle != null) {
      for (final route in importedRoutes) {
        if (route.title == selectedTitle) {
          selectedRoute = route;
          break;
        }
      }
    }
    if (!mounted) return;
    setState(() {
      _importedRoutes
        ..clear()
        ..addAll(importedRoutes);
      _favoriteRouteTitles
        ..clear()
        ..addAll(titles);
    });
    if (selectedRoute == null) {
      widget.controller.clearSelectedRoute();
      if (selectedTitle != null) {
        await prefs.remove(_selectedRoutePrefsKey);
      }
    } else {
      widget.controller.selectRoute(selectedRoute.toRideRouteSelection());
    }
  }

  Future<void> _saveFavoriteRoutes() async {
    final prefs = await SharedPreferences.getInstance();
    final titles = _favoriteRouteTitles.toList()..sort();
    await prefs.setStringList(_favoriteRoutesPrefsKey, titles);
  }

  Future<void> _saveImportedRoutes() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setStringList(
      _importedRoutesPrefsKey,
      _importedRoutes.map((route) => jsonEncode(route.toJson())).toList(),
    );
  }

  Future<void> _saveSelectedRouteTitle(String title) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_selectedRoutePrefsKey, title);
  }

  Future<void> _clearSelectedRouteTitle() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_selectedRoutePrefsKey);
  }

  void _toggleFavorite(_RouteListEntry route) {
    setState(() {
      if (!_favoriteRouteTitles.add(route.title)) {
        _favoriteRouteTitles.remove(route.title);
      }
    });
    unawaited(_saveFavoriteRoutes());
  }

  Future<void> _confirmDeleteImportedRoute(_RouteListEntry route) async {
    if (!route.imported) {
      _showUiMessage('删除路线', '默认路线不能删除');
      return;
    }

    final confirmed = await _showRouteDeleteConfirmDialog(context, route.title);
    if (!confirmed || !mounted) return;
    _deleteImportedRoute(route);
  }

  void _deleteImportedRoute(_RouteListEntry route) {
    setState(() {
      _importedRoutes.removeWhere((item) => item.title == route.title);
      _favoriteRouteTitles.remove(route.title);
    });
    if (widget.controller.selectedRoute.value?.title == route.title) {
      widget.controller.clearSelectedRoute(route.title);
      unawaited(_clearSelectedRouteTitle());
    }
    unawaited(_saveImportedRoutes());
    unawaited(_saveFavoriteRoutes());
    _showUiMessage('删除路线', '已删除 ${route.title}');
  }

  void _selectRouteForRide(_RouteListEntry route) {
    widget.controller.selectRoute(route.toRideRouteSelection());
    setState(() {});
    unawaited(_saveSelectedRouteTitle(route.title));
    _showUiMessage('当前骑行路线', '已选择 ${route.title}');
  }

  Future<void> _importGpxRoute() async {
    if (_importingRoute) return;
    _importingRoute = true;

    try {
      final result = await FilePicker.platform.pickFiles(
        type: FileType.any,
        allowMultiple: false,
        withData: true,
        dialogTitle: '选择路书文件',
      );
      if (result == null || result.files.isEmpty) return;
      if (!mounted) return;

      setState(() {
        _routeFabExpanded = false;
      });

      final file = result.files.single;
      final content = await _readPickedGpxFile(file);
      final parsed = _parseGpxRoute(
        content,
        fileName: file.name,
        fallbackVariant: _allRoutes.length,
      );
      final route = parsed.copyWith(title: _uniqueRouteTitle(parsed.title));
      if (!mounted) return;

      setState(() {
        _importedRoutes.insert(0, route);
      });
      _selectRouteMode(2);
      await _saveImportedRoutes();
      _showUiMessage('导入路线', '已导入 ${route.title}');
    } on FormatException catch (error) {
      _showUiMessage('导入失败', error.message);
    } on MissingPluginException {
      _showUiMessage('导入失败', '文件选择器插件未注册，请安装最新构建');
    } on PlatformException catch (error) {
      _showUiMessage('导入失败', error.message ?? error.code);
    } catch (_) {
      _showUiMessage('导入失败', '请选择有效的 GPX 文件');
    } finally {
      _importingRoute = false;
      if (mounted) {
        setState(() {});
      }
    }
  }

  Future<String> _readPickedGpxFile(PlatformFile file) async {
    final bytes = file.bytes;
    if (bytes != null) {
      return utf8.decode(bytes, allowMalformed: true);
    }

    final path = file.path;
    if (path == null || path.isEmpty) {
      throw const FormatException('无法读取所选 GPX 文件');
    }
    return io.File(path).readAsString();
  }

  String _uniqueRouteTitle(String title) {
    final existingTitles = _allRoutes.map((route) => route.title).toSet();
    if (!existingTitles.contains(title)) return title;

    var index = 2;
    while (existingTitles.contains('$title ($index)')) {
      index += 1;
    }
    return '$title ($index)';
  }

  @override
  Widget build(BuildContext context) {
    final routes = _allRoutes;
    final importedCount = _importedRoutes.length;
    final visibleCount = _routesForMode(_modeIndex).length;
    final filterPrefix = _routeFilterIndex == 0 ? '' : '$_routeFilterLabel ';
    final routeCountLabel = switch (_modeIndex) {
      1 => '$filterPrefix收藏路线（$visibleCount）',
      2 => '$filterPrefix导入路线（$visibleCount）',
      _ => '$filterPrefix我的路线（$visibleCount）',
    };

    return Stack(
      children: [
        Column(
          children: [
            // 固定子头：模式分段 + 搜索 + 计数（无第二顶部栏）
            Padding(
              padding: const EdgeInsets.fromLTRB(18, 12, 18, 0),
              child: Column(
                children: [
                  _RouteModeTabs(
                    selectedIndex: _modeIndex,
                    controller: _routePageController,
                    counts: [
                      routes.length,
                      _favoriteRouteTitles.length,
                      importedCount,
                    ],
                    onSelect: _selectRouteMode,
                  ),
                  const SizedBox(height: 12),
                  _RouteSearchBar(
                    filterLabel: _routeFilterLabel,
                    onFilterTap: _openRouteFilterSheet,
                  ),
                  const SizedBox(height: 14),
                  Align(
                    alignment: Alignment.centerLeft,
                    child: Text(
                      routeCountLabel,
                      style: TextStyle(
                        color: Colors.white.withOpacity(0.72),
                        fontSize: 16,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 12),
            // 单一滚动区：路线卡片列表
            Expanded(
              child: PageView.builder(
                controller: _routePageController,
                physics: const PageScrollPhysics(
                  parent: BouncingScrollPhysics(),
                ),
                itemCount: _routeModeCount,
                onPageChanged: _handleRouteModePageChanged,
                itemBuilder: (context, index) => _buildRouteModePage(index),
              ),
            ),
          ],
        ),
        Positioned(
          right: 18,
          bottom: 18,
          child: _RouteImportFab(
            expanded: _routeFabExpanded,
            busy: _importingRoute,
            onToggle: () {
              setState(() => _routeFabExpanded = !_routeFabExpanded);
            },
            onImportGpx: () {
              unawaited(_importGpxRoute());
            },
            onCreateRoute: () {
              setState(() => _routeFabExpanded = false);
              _showUiMessage('创建路书', '创建路书功能入口已打开');
            },
          ),
        ),
      ],
    );
  }

  Widget _buildRouteModePage(int modeIndex) {
    final visibleRoutes = _routesForMode(modeIndex);
    if (visibleRoutes.isEmpty) {
      return _RouteEmptyState(
        modeIndex: modeIndex,
        onImport: () {
          unawaited(_importGpxRoute());
        },
      );
    }

    return ListView.separated(
      physics: const BouncingScrollPhysics(),
      padding: const EdgeInsets.fromLTRB(18, 0, 18, 112),
      itemCount: visibleRoutes.length,
      separatorBuilder: (_, __) => const SizedBox(height: 10),
      itemBuilder: (context, index) {
        final route = visibleRoutes[index];
        final selectedForRide =
            widget.controller.selectedRoute.value?.title == route.title;
        return _RouteListCard(
          title: route.title,
          date: route.date,
          distance: route.distance,
          climb: route.climb,
          duration: route.duration,
          difficulty: route.difficulty,
          difficultyColor: route.difficultyColor,
          variant: route.variant,
          track: route.track,
          favorited: _favoriteRouteTitles.contains(route.title),
          selectedForRide: selectedForRide,
          onFavoriteToggle: () => _toggleFavorite(route),
          onSelectForRide: () => _selectRouteForRide(route),
          onDelete: route.imported
              ? () => unawaited(_confirmDeleteImportedRoute(route))
              : null,
        );
      },
    );
  }
}

class _RouteListEntry {
  const _RouteListEntry({
    required this.title,
    required this.date,
    required this.distance,
    required this.climb,
    required this.duration,
    required this.difficulty,
    required this.difficultyColor,
    required this.variant,
    this.imported = false,
    this.track = const <_GpxPoint>[],
  });

  final String title;
  final String date;
  final String distance;
  final String climb;
  final String duration;
  final String difficulty;
  final Color difficultyColor;
  final int variant;
  final bool imported;
  final List<_GpxPoint> track;

  _RouteListEntry copyWith({
    String? title,
    String? date,
    String? distance,
    String? climb,
    String? duration,
    String? difficulty,
    Color? difficultyColor,
    int? variant,
    bool? imported,
    List<_GpxPoint>? track,
  }) {
    return _RouteListEntry(
      title: title ?? this.title,
      date: date ?? this.date,
      distance: distance ?? this.distance,
      climb: climb ?? this.climb,
      duration: duration ?? this.duration,
      difficulty: difficulty ?? this.difficulty,
      difficultyColor: difficultyColor ?? this.difficultyColor,
      variant: variant ?? this.variant,
      imported: imported ?? this.imported,
      track: track ?? this.track,
    );
  }

  Map<String, Object?> toJson() {
    return {
      'title': title,
      'date': date,
      'distance': distance,
      'climb': climb,
      'duration': duration,
      'difficulty': difficulty,
      'difficultyColor': difficultyColor.value,
      'variant': variant,
      'imported': imported,
      'track': track.map((point) => point.toJson()).toList(),
    };
  }

  static _RouteListEntry? tryFromJson(String source) {
    try {
      final data = jsonDecode(source);
      if (data is! Map<String, dynamic>) return null;

      return _RouteListEntry(
        title: _stringValue(data['title'], '导入路线'),
        date: _stringValue(data['date'], '未知时间'),
        distance: _stringValue(data['distance'], '0.00'),
        climb: _stringValue(data['climb'], '0'),
        duration: _stringValue(data['duration'], '00:00:00'),
        difficulty: _stringValue(data['difficulty'], '简单'),
        difficultyColor: Color(_intValue(data['difficultyColor'], 0xFF62D729)),
        variant: _intValue(data['variant'], 0),
        imported: _boolValue(data['imported'], true),
        track: _trackValue(data['track']),
      );
    } catch (_) {
      return null;
    }
  }

  static String _stringValue(Object? value, String fallback) {
    if (value is String && value.trim().isNotEmpty) return value;
    return fallback;
  }

  static int _intValue(Object? value, int fallback) {
    if (value is int) return value;
    if (value is num) return value.toInt();
    if (value is String) return int.tryParse(value) ?? fallback;
    return fallback;
  }

  static bool _boolValue(Object? value, bool fallback) {
    if (value is bool) return value;
    if (value is String) return value.toLowerCase() == 'true';
    return fallback;
  }

  static List<_GpxPoint> _trackValue(Object? value) {
    if (value is! List) return const <_GpxPoint>[];
    return value
        .map(_GpxPoint.tryFromJson)
        .whereType<_GpxPoint>()
        .toList(growable: false);
  }
}

extension _RouteListEntrySelection on _RouteListEntry {
  RideRouteSelection toRideRouteSelection() {
    return RideRouteSelection(
      title: title,
      date: date,
      distance: distance,
      climb: climb,
      duration: duration,
      difficulty: difficulty,
      difficultyColorValue: difficultyColor.value,
      variant: variant,
      track: track
          .map(
            (point) => RideRoutePoint(
              latitude: point.lat,
              longitude: point.lon,
              altitudeM: point.ele,
            ),
          )
          .toList(growable: false),
    );
  }
}

class _RouteImportFab extends StatefulWidget {
  const _RouteImportFab({
    required this.expanded,
    required this.busy,
    required this.onToggle,
    required this.onImportGpx,
    required this.onCreateRoute,
  });

  final bool expanded;
  final bool busy;
  final VoidCallback onToggle;
  final VoidCallback onImportGpx;
  final VoidCallback onCreateRoute;

  @override
  State<_RouteImportFab> createState() => _RouteImportFabState();
}

class _RouteImportFabState extends State<_RouteImportFab>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 120),
      reverseDuration: const Duration(milliseconds: 90),
      value: widget.expanded ? 1 : 0,
    );
  }

  @override
  void didUpdateWidget(covariant _RouteImportFab oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.expanded != oldWidget.expanded) {
      if (widget.expanded) {
        unawaited(_controller.forward());
      } else {
        unawaited(_controller.reverse());
      }
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    const actionSpacing = 12.0;
    const actionStep = 68.0;
    final actionCount = 2;
    final stackHeight = 64.0 + actionSpacing + actionStep * actionCount;

    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.end,
      children: [
        SizedBox(
          width: 164,
          height: stackHeight,
          child: Stack(
            alignment: Alignment.bottomRight,
            children: [
              _RouteFabAction(
                label: '创建路书',
                icon: Icons.edit,
                color: const Color(0xFFFFB000),
                busy: false,
                onTap: widget.onCreateRoute,
                animation: CurvedAnimation(
                  parent: _controller,
                  curve: const Interval(0.38, 1, curve: Curves.easeOutCubic),
                  reverseCurve:
                      const Interval(0.38, 1, curve: Curves.easeInCubic),
                ),
                bottom: 64 + actionSpacing + actionStep,
              ),
              _RouteFabAction(
                label: '导入路书',
                icon: Icons.file_upload_outlined,
                color: _RideColors.orange,
                busy: widget.busy,
                onTap: widget.busy ? null : widget.onImportGpx,
                animation: CurvedAnimation(
                  parent: _controller,
                  curve: const Interval(0, 0.62, curve: Curves.easeOutCubic),
                  reverseCurve:
                      const Interval(0, 0.62, curve: Curves.easeInCubic),
                ),
                bottom: 64 + actionSpacing,
              ),
              _RouteFabToggleButton(
                color: const Color(0xFFFFB000),
                size: 64,
                onTap: widget.onToggle,
                animation: CurvedAnimation(
                  parent: _controller,
                  curve: Curves.easeInOutCubic,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _RouteFabAction extends StatelessWidget {
  const _RouteFabAction({
    required this.label,
    required this.icon,
    required this.color,
    required this.onTap,
    required this.animation,
    required this.bottom,
    this.busy = false,
  });

  final String label;
  final IconData icon;
  final Color color;
  final VoidCallback? onTap;
  final Animation<double> animation;
  final double bottom;
  final bool busy;

  @override
  Widget build(BuildContext context) {
    return Positioned(
      right: 0,
      bottom: bottom,
      child: AnimatedBuilder(
        animation: animation,
        builder: (context, child) {
          final progress = animation.value;
          return IgnorePointer(
            ignoring: progress <= 0.01 || busy,
            child: Opacity(
              opacity: progress,
              child: Transform.translate(
                offset: Offset(0, 34 * (1 - progress)),
                child: Transform.scale(
                  scale: 0.82 + 0.18 * progress,
                  alignment: Alignment.bottomRight,
                  child: child,
                ),
              ),
            ),
          );
        },
        child: GestureDetector(
          behavior: HitTestBehavior.opaque,
          onTap: onTap,
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                height: 34,
                padding: const EdgeInsets.symmetric(horizontal: 12),
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: const Color(0xFF101720).withOpacity(0.92),
                  borderRadius: BorderRadius.circular(17),
                  border: Border.all(color: Colors.white.withOpacity(0.10)),
                  boxShadow: [
                    BoxShadow(
                      color: Colors.black.withOpacity(0.24),
                      blurRadius: 16,
                      offset: const Offset(0, 6),
                    ),
                  ],
                ),
                child: Text(
                  label,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 13,
                    fontWeight: FontWeight.w900,
                  ),
                ),
              ),
              const SizedBox(width: 10),
              IgnorePointer(
                child: _RouteFabButton(
                  icon: icon,
                  color: color,
                  size: 56,
                  busy: busy,
                  onTap: null,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _RouteFabToggleButton extends StatelessWidget {
  const _RouteFabToggleButton({
    required this.color,
    required this.size,
    required this.onTap,
    required this.animation,
  });

  final Color color;
  final double size;
  final VoidCallback? onTap;
  final Animation<double> animation;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: color,
      shape: const CircleBorder(),
      elevation: 10,
      shadowColor: Colors.black.withOpacity(0.52),
      child: InkWell(
        customBorder: const CircleBorder(),
        onTap: onTap,
        child: SizedBox(
          width: size,
          height: size,
          child: Center(
            child: AnimatedBuilder(
              animation: animation,
              builder: (context, _) {
                return CustomPaint(
                  size: Size.square(size * 0.44),
                  painter: _RouteFabToggleIconPainter(animation.value),
                );
              },
            ),
          ),
        ),
      ),
    );
  }
}

class _RouteFabToggleIconPainter extends CustomPainter {
  const _RouteFabToggleIconPainter(this.progress);

  final double progress;

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final length = size.shortestSide * (0.76 - 0.08 * progress);
    final paint = Paint()
      ..color = Colors.white
      ..strokeWidth = 3.8
      ..strokeCap = StrokeCap.round
      ..style = PaintingStyle.stroke;

    void drawLine(double angle) {
      final vector = Offset(math.cos(angle), math.sin(angle)) * (length / 2);
      canvas.drawLine(center - vector, center + vector, paint);
    }

    drawLine((math.pi / 4) * progress);
    drawLine((math.pi / 2) + (math.pi / 4) * progress);
  }

  @override
  bool shouldRepaint(covariant _RouteFabToggleIconPainter oldDelegate) {
    return oldDelegate.progress != progress;
  }
}

class _RouteFabButton extends StatelessWidget {
  const _RouteFabButton({
    required this.icon,
    required this.color,
    required this.size,
    required this.onTap,
    this.busy = false,
    this.turn = 0,
  });

  final IconData icon;
  final Color color;
  final double size;
  final VoidCallback? onTap;
  final bool busy;
  final double turn;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: color,
      shape: const CircleBorder(),
      elevation: 10,
      shadowColor: Colors.black.withOpacity(0.52),
      child: InkWell(
        customBorder: const CircleBorder(),
        onTap: onTap,
        child: SizedBox(
          width: size,
          height: size,
          child: Center(
            child: busy
                ? const SizedBox(
                    width: 22,
                    height: 22,
                    child: CircularProgressIndicator(
                      strokeWidth: 2.4,
                      valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                    ),
                  )
                : AnimatedRotation(
                    turns: turn,
                    duration: const Duration(milliseconds: 220),
                    curve: Curves.easeOutCubic,
                    child: Icon(
                      icon,
                      color: Colors.white,
                      size: size * 0.44,
                    ),
                  ),
          ),
        ),
      ),
    );
  }
}

_RouteListEntry _parseGpxRoute(
  String source, {
  required String fileName,
  required int fallbackVariant,
}) {
  final points = _extractGpxPoints(source);
  if (points.length < 2) {
    throw const FormatException('GPX 文件中没有足够的路线点');
  }

  final distanceKm = _calculateRouteDistanceKm(points);
  final climbMeters = _calculateRouteClimbMeters(points);
  final startedAt = _firstGpxTime(source) ?? DateTime.now();
  final endedAt = _lastGpxTime(source);
  final duration = endedAt != null && endedAt.isAfter(startedAt)
      ? endedAt.difference(startedAt)
      : Duration(minutes: math.max(1, (distanceKm / 22 * 60).round()));

  return _RouteListEntry(
    title: _extractGpxRouteName(source, fileName),
    date: _formatImportedRouteDate(startedAt),
    distance: distanceKm.toStringAsFixed(2),
    climb: climbMeters.round().toString(),
    duration: _formatRouteDuration(duration),
    difficulty: _routeDifficulty(distanceKm, climbMeters),
    difficultyColor: _routeDifficultyColor(distanceKm, climbMeters),
    variant: fallbackVariant % 6,
    imported: true,
    track: _sampleGpxPoints(points),
  );
}

List<_GpxPoint> _sampleGpxPoints(
  List<_GpxPoint> points, {
  int maxPoints = 800,
}) {
  if (points.length <= maxPoints) {
    return List<_GpxPoint>.unmodifiable(points);
  }

  final sampled = <_GpxPoint>[];
  final step = (points.length - 1) / (maxPoints - 1);
  for (var i = 0; i < maxPoints; i++) {
    sampled.add(points[(i * step).round()]);
  }
  return List<_GpxPoint>.unmodifiable(sampled);
}

List<_GpxPoint> _extractGpxPoints(String source) {
  final matches = RegExp(
    r'<(?:\w+:)?(?:trkpt|rtept)\b([^>]*)>([\s\S]*?)</(?:\w+:)?(?:trkpt|rtept)>',
    caseSensitive: false,
  ).allMatches(source);
  final points = <_GpxPoint>[];

  for (final match in matches) {
    final attributes = match.group(1) ?? '';
    final body = match.group(2) ?? '';
    final lat = _extractGpxAttribute(attributes, 'lat');
    final lon = _extractGpxAttribute(attributes, 'lon');
    if (lat == null || lon == null) continue;

    points.add(
      _GpxPoint(
        lat: lat,
        lon: lon,
        ele: _extractGpxTagDouble(body, 'ele'),
      ),
    );
  }

  final selfClosingMatches = RegExp(
    r'<(?:\w+:)?(?:trkpt|rtept)\b([^>]*)/>',
    caseSensitive: false,
  ).allMatches(source);
  for (final match in selfClosingMatches) {
    final attributes = match.group(1) ?? '';
    final lat = _extractGpxAttribute(attributes, 'lat');
    final lon = _extractGpxAttribute(attributes, 'lon');
    if (lat == null || lon == null) continue;

    points.add(_GpxPoint(lat: lat, lon: lon, ele: null));
  }

  return points;
}

double? _extractGpxAttribute(String attributes, String name) {
  final match = RegExp(
    '$name\\s*=\\s*["\\\']([^"\\\']+)["\\\']',
    caseSensitive: false,
  ).firstMatch(attributes);
  if (match == null) return null;
  return double.tryParse(match.group(1) ?? '');
}

double? _extractGpxTagDouble(String source, String tagName) {
  final match = RegExp(
    '<(?:\\w+:)?$tagName[^>]*>([^<]+)</(?:\\w+:)?$tagName>',
    caseSensitive: false,
  ).firstMatch(source);
  if (match == null) return null;
  return double.tryParse((match.group(1) ?? '').trim());
}

String _extractGpxRouteName(String source, String fileName) {
  for (final pattern in const [
    r'<(?:\w+:)?trk\b[\s\S]*?<(?:\w+:)?name[^>]*>([^<]+)</(?:\w+:)?name>',
    r'<(?:\w+:)?rte\b[\s\S]*?<(?:\w+:)?name[^>]*>([^<]+)</(?:\w+:)?name>',
    r'<(?:\w+:)?metadata\b[\s\S]*?<(?:\w+:)?name[^>]*>([^<]+)</(?:\w+:)?name>',
  ]) {
    final match = RegExp(pattern, caseSensitive: false).firstMatch(source);
    final value = match?.group(1)?.trim();
    if (value != null && value.isNotEmpty) {
      return _decodeXmlText(value);
    }
  }

  final dotIndex = fileName.lastIndexOf('.');
  final name = dotIndex > 0 ? fileName.substring(0, dotIndex) : fileName;
  return name.trim().isEmpty ? '导入路线' : name.trim();
}

String _decodeXmlText(String source) {
  return source
      .replaceAll('&amp;', '&')
      .replaceAll('&lt;', '<')
      .replaceAll('&gt;', '>')
      .replaceAll('&quot;', '"')
      .replaceAll('&apos;', "'");
}

DateTime? _firstGpxTime(String source) {
  final match = RegExp(
    r'<(?:\w+:)?time[^>]*>([^<]+)</(?:\w+:)?time>',
    caseSensitive: false,
  ).firstMatch(source);
  return _parseGpxTime(match?.group(1));
}

DateTime? _lastGpxTime(String source) {
  final matches = RegExp(
    r'<(?:\w+:)?time[^>]*>([^<]+)</(?:\w+:)?time>',
    caseSensitive: false,
  ).allMatches(source);
  if (matches.isEmpty) return null;
  return _parseGpxTime(matches.last.group(1));
}

DateTime? _parseGpxTime(String? source) {
  if (source == null) return null;
  return DateTime.tryParse(source.trim())?.toLocal();
}

double _calculateRouteDistanceKm(List<_GpxPoint> points) {
  var meters = 0.0;
  for (var i = 1; i < points.length; i++) {
    meters += _haversineMeters(points[i - 1], points[i]);
  }
  return meters / 1000;
}

double _calculateRouteClimbMeters(List<_GpxPoint> points) {
  var climb = 0.0;
  for (var i = 1; i < points.length; i++) {
    final previous = points[i - 1].ele;
    final current = points[i].ele;
    if (previous == null || current == null) continue;

    final gain = current - previous;
    if (gain > 1.5) {
      climb += gain;
    }
  }
  return climb;
}

double _haversineMeters(_GpxPoint a, _GpxPoint b) {
  const earthRadiusMeters = 6371000.0;
  final lat1 = _degreesToRadians(a.lat);
  final lat2 = _degreesToRadians(b.lat);
  final dLat = _degreesToRadians(b.lat - a.lat);
  final dLon = _degreesToRadians(b.lon - a.lon);
  final h = math.sin(dLat / 2) * math.sin(dLat / 2) +
      math.cos(lat1) *
          math.cos(lat2) *
          math.sin(dLon / 2) *
          math.sin(dLon / 2);
  return earthRadiusMeters * 2 * math.atan2(math.sqrt(h), math.sqrt(1 - h));
}

double _degreesToRadians(double degrees) {
  return degrees * math.pi / 180;
}

String _formatImportedRouteDate(DateTime date) {
  return '${date.year.toString().padLeft(4, '0')}/'
      '${date.month.toString().padLeft(2, '0')}/'
      '${date.day.toString().padLeft(2, '0')}  '
      '${date.hour.toString().padLeft(2, '0')}:'
      '${date.minute.toString().padLeft(2, '0')}';
}

String _formatRouteDuration(Duration duration) {
  final hours = duration.inHours;
  final minutes = duration.inMinutes.remainder(60);
  final seconds = duration.inSeconds.remainder(60);
  return '${hours.toString().padLeft(2, '0')}:'
      '${minutes.toString().padLeft(2, '0')}:'
      '${seconds.toString().padLeft(2, '0')}';
}

String _routeDifficulty(double distanceKm, double climbMeters) {
  if (distanceKm >= 90 || climbMeters >= 1000) return '困难';
  if (distanceKm >= 45 || climbMeters >= 450) return '中等';
  return '简单';
}

Color _routeDifficultyColor(double distanceKm, double climbMeters) {
  if (distanceKm >= 90 || climbMeters >= 1000) {
    return const Color(0xFFFF3B5F);
  }
  if (distanceKm >= 45 || climbMeters >= 450) {
    return const Color(0xFFA46AFF);
  }
  return const Color(0xFF62D729);
}

class _GpxPoint {
  const _GpxPoint({
    required this.lat,
    required this.lon,
    required this.ele,
  });

  final double lat;
  final double lon;
  final double? ele;

  Map<String, Object?> toJson() {
    return {
      'lat': lat,
      'lon': lon,
      if (ele != null) 'ele': ele,
    };
  }

  static _GpxPoint? tryFromJson(Object? value) {
    if (value is! Map) return null;
    final lat = _jsonDouble(value['lat']);
    final lon = _jsonDouble(value['lon']);
    if (lat == null || lon == null) return null;
    return _GpxPoint(
      lat: lat,
      lon: lon,
      ele: _jsonDouble(value['ele']),
    );
  }

  static double? _jsonDouble(Object? value) {
    if (value is num) return value.toDouble();
    if (value is String) return double.tryParse(value);
    return null;
  }
}

List<_GpxPoint> _gpxPointsFromRideRoute(List<RideRoutePoint> track) {
  return track
      .map(
        (point) => _GpxPoint(
          lat: point.latitude,
          lon: point.longitude,
          ele: point.altitudeM,
        ),
      )
      .toList(growable: false);
}

void _openSelectedRideRoute(RideRouteSelection route) {
  _openRidePage(
    () => _RideRouteDetailPage(
      title: route.title,
      date: route.date,
      distance: route.distance,
      climb: route.climb,
      duration: route.duration,
      difficulty: route.difficulty,
      difficultyColor: Color(route.difficultyColorValue),
      variant: route.variant,
      track: _gpxPointsFromRideRoute(route.track),
    ),
  );
}

List<double> _routeElevationValues(List<_GpxPoint> track) {
  final values = track
      .map((point) => point.ele)
      .whereType<double>()
      .where((value) => value.isFinite)
      .toList(growable: false);
  if (values.length < 2) {
    return const <double>[
      120,
      180,
      260,
      420,
      700,
      980,
      1180,
      1268,
      1040,
      760,
      520,
      360,
      240,
      160,
    ];
  }
  return _sampleDoubleValues(values, maxValues: 80);
}

List<double> _sampleDoubleValues(
  List<double> values, {
  required int maxValues,
}) {
  if (values.length <= maxValues) return values;
  final sampled = <double>[];
  final step = (values.length - 1) / (maxValues - 1);
  for (var i = 0; i < maxValues; i++) {
    sampled.add(values[(i * step).round()]);
  }
  return sampled;
}

String _routePointLabel(_GpxPoint? point) {
  if (point == null) return '杭州市 西湖区';
  return '${point.lat.toStringAsFixed(5)}, ${point.lon.toStringAsFixed(5)}';
}

String _routeMaxElevationLabel(List<_GpxPoint> track) {
  final elevations = track
      .map((point) => point.ele)
      .whereType<double>()
      .where((value) => value.isFinite)
      .toList(growable: false);
  if (elevations.isEmpty) return '未提供';
  final maxElevation = elevations.reduce(math.max);
  return '${maxElevation.round()} m';
}

class _RouteEmptyState extends StatelessWidget {
  const _RouteEmptyState({
    required this.modeIndex,
    required this.onImport,
  });

  final int modeIndex;
  final VoidCallback onImport;

  @override
  Widget build(BuildContext context) {
    final label = modeIndex == 1 ? '暂无收藏路线' : '暂无导入路线';
    final icon = modeIndex == 1 ? Icons.star_border : Icons.file_upload_outlined;
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, color: Colors.white.withOpacity(0.36), size: 42),
          const SizedBox(height: 12),
          Text(
            label,
            style: TextStyle(
              color: Colors.white.withOpacity(0.58),
              fontSize: 16,
              fontWeight: FontWeight.w800,
            ),
          ),
          if (modeIndex == 2) ...[
            const SizedBox(height: 18),
            FilledButton.icon(
              onPressed: onImport,
              style: FilledButton.styleFrom(
                backgroundColor: _RideColors.orange,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(
                  horizontal: 18,
                  vertical: 12,
                ),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(999),
                ),
              ),
              icon: const Icon(Icons.file_upload_outlined, size: 20),
              label: const Text(
                '导入路书',
                style: TextStyle(fontWeight: FontWeight.w900),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _RouteModeTabs extends StatelessWidget {
  const _RouteModeTabs({
    required this.selectedIndex,
    required this.controller,
    required this.counts,
    required this.onSelect,
  });

  final int selectedIndex;
  final PageController controller;
  final List<int> counts;
  final ValueChanged<int> onSelect;

  @override
  Widget build(BuildContext context) {
    final labels = [
      '我的路线（${counts[0]}）',
      '收藏路线（${counts[1]}）',
      '导入路线（${counts[2]}）',
    ];
    return _OuterFrame(
      padding: const EdgeInsets.all(4),
      child: _AnimatedSegmentTabs(
        labels: labels,
        selectedIndex: selectedIndex,
        controller: controller,
        height: 48,
        borderRadius: BorderRadius.circular(10),
        indicatorColor: _RideColors.orange.withOpacity(0.13),
        indicatorBorder: Border.all(
          color: _RideColors.orange.withOpacity(0.85),
        ),
        activeColor: _RideColors.orange,
        inactiveColor: Colors.white.withOpacity(0.70),
        fontSize: 14,
        fontWeight: FontWeight.w900,
        onSelect: onSelect,
      ),
    );
  }
}

class _RouteSearchBar extends StatelessWidget {
  const _RouteSearchBar({
    required this.filterLabel,
    required this.onFilterTap,
  });

  final String filterLabel;
  final VoidCallback onFilterTap;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: Container(
            height: 48,
            padding: const EdgeInsets.symmetric(horizontal: 16),
            decoration: BoxDecoration(
              color: Colors.white.withOpacity(0.07),
              borderRadius: BorderRadius.circular(15),
            ),
            child: Row(
              children: [
                Icon(Icons.search, color: Colors.white.withOpacity(0.64), size: 23),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    '搜索路线名称或地点',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      color: Colors.white.withOpacity(0.48),
                      fontSize: 15,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(width: 12),
        InkWell(
          borderRadius: BorderRadius.circular(15),
          onTap: onFilterTap,
          child: Container(
            height: 48,
            padding: const EdgeInsets.symmetric(horizontal: 18),
            decoration: BoxDecoration(
              color: Colors.white.withOpacity(0.08),
              borderRadius: BorderRadius.circular(15),
            ),
            child: Row(
              children: [
                Text(
                  filterLabel,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 15,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(width: 6),
                Icon(
                  Icons.keyboard_arrow_down,
                  color: Colors.white.withOpacity(0.78),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

class _RouteListCard extends StatefulWidget {
  const _RouteListCard({
    required this.title,
    required this.date,
    required this.distance,
    required this.climb,
    required this.duration,
    required this.difficulty,
    required this.difficultyColor,
    required this.variant,
    required this.track,
    required this.favorited,
    required this.selectedForRide,
    required this.onFavoriteToggle,
    required this.onSelectForRide,
    this.onDelete,
  });

  final String title;
  final String date;
  final String distance;
  final String climb;
  final String duration;
  final String difficulty;
  final Color difficultyColor;
  final int variant;
  final List<_GpxPoint> track;
  final bool favorited;
  final bool selectedForRide;
  final VoidCallback onFavoriteToggle;
  final VoidCallback onSelectForRide;
  final VoidCallback? onDelete;

  @override
  State<_RouteListCard> createState() => _RouteListCardState();
}

class _RouteListCardState extends State<_RouteListCard> {
  void _openRoute() {
    _openRidePage(
      () => _RideRouteDetailPage(
        title: widget.title,
        date: widget.date,
        distance: widget.distance,
        climb: widget.climb,
        duration: widget.duration,
        difficulty: widget.difficulty,
        difficultyColor: widget.difficultyColor,
        variant: widget.variant,
        track: widget.track,
        favorited: widget.favorited,
        onFavoriteToggle: widget.onFavoriteToggle,
      ),
    );
  }

  void _toggleFavorite() {
    final willFavorite = !widget.favorited;
    widget.onFavoriteToggle();
    _showUiMessage(
      '收藏',
      willFavorite ? '已收藏 ${widget.title}' : '已取消收藏 ${widget.title}',
    );
  }

  @override
  Widget build(BuildContext context) {
    final title = widget.title;
    final date = widget.date;
    final distance = widget.distance;
    final climb = widget.climb;
    final duration = widget.duration;
    final difficulty = widget.difficulty;
    final difficultyColor = widget.difficultyColor;
    final variant = widget.variant;

    return _GlassPanel(
      padding: EdgeInsets.zero,
      child: LayoutBuilder(
        builder: (context, constraints) {
          final compact = constraints.maxWidth < 360;
          final cardHeight = compact ? 214.0 : 194.0;
          final mapWidth = compact ? 118.0 : 148.0;
          final titleSize = compact ? 18.0 : 20.0;

          return SizedBox(
            height: cardHeight,
            child: Row(
              children: [
                GestureDetector(
                  behavior: HitTestBehavior.opaque,
                  onTap: _openRoute,
                  child: SizedBox(
                    width: mapWidth,
                    child: ClipRRect(
                      borderRadius: const BorderRadius.horizontal(
                        left: Radius.circular(14),
                      ),
                      child: CustomPaint(
                        painter: _RouteMapPainter(
                          variant: variant,
                          gpxTrack: widget.track,
                        ),
                        child: const SizedBox.expand(),
                      ),
                    ),
                  ),
                ),
                Expanded(
                  child: Padding(
                    padding: EdgeInsets.fromLTRB(
                      compact ? 12 : 16,
                      16,
                      12,
                      12,
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Expanded(
                          child: GestureDetector(
                            behavior: HitTestBehavior.opaque,
                            onTap: _openRoute,
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  title,
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                  style: TextStyle(
                                    color: Colors.white,
                                    fontSize: titleSize,
                                    fontWeight: FontWeight.w900,
                                  ),
                                ),
                                const SizedBox(height: 6),
                                Text(
                                  date,
                                  style: TextStyle(
                                    color: Colors.white.withOpacity(0.60),
                                    fontSize: 13,
                                    fontWeight: FontWeight.w700,
                                  ),
                                ),
                                const SizedBox(height: 10),
                                Wrap(
                                  spacing: 8,
                                  runSpacing: 4,
                                  children: [
                                    _RouteBadge(
                                      label: '公路',
                                      color: _RideColors.orange,
                                    ),
                                    _RouteBadge(
                                      label: '难度 $difficulty',
                                      color: difficultyColor,
                                    ),
                                    if (widget.selectedForRide)
                                      const _RouteBadge(
                                        label: '当前',
                                        color: Color(0xFF3BE23E),
                                      ),
                                  ],
                                ),
                                const Spacer(),
                                Wrap(
                                  spacing: compact ? 10 : 14,
                                  runSpacing: 4,
                                  children: [
                                    _RouteMetric(value: distance, unit: 'km'),
                                    _RouteMetric(value: climb, unit: 'm'),
                                    _RouteMetric(value: duration, unit: ''),
                                  ],
                                ),
                              ],
                            ),
                          ),
                        ),
                        Divider(
                          color: Colors.white.withOpacity(0.08),
                          height: 16,
                        ),
                        SizedBox(
                          height: 34,
                          child: Row(
                            mainAxisAlignment: MainAxisAlignment.end,
                            children: [
                              _RouteActionButton(
                                icon: Icons.navigation,
                                active: widget.selectedForRide,
                                tooltip: '设为当前骑行路线',
                                onTap: widget.onSelectForRide,
                              ),
                              const SizedBox(width: 14),
                              _RouteActionButton(
                                icon: widget.favorited
                                    ? Icons.star
                                    : Icons.star_border,
                                active: widget.favorited,
                                tooltip: '收藏',
                                onTap: _toggleFavorite,
                              ),
                              const SizedBox(width: 14),
                              _RouteActionButton(
                                icon: Icons.share_outlined,
                                tooltip: '分享',
                                onTap: () => _shareRouteSummary(
                                  context,
                                  title: title,
                                ),
                              ),
                              const SizedBox(width: 14),
                              _RouteActionButton(
                                icon: Icons.more_horiz,
                                tooltip: '更多',
                                onTap: () => _showRouteMoreActions(
                                  context,
                                  title: title,
                                  date: date,
                                  distance: distance,
                                  climb: climb,
                                  duration: duration,
                                  difficulty: difficulty,
                                  onDelete: widget.onDelete,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}

class _RouteActionButton extends StatelessWidget {
  const _RouteActionButton({
    required this.icon,
    required this.tooltip,
    required this.onTap,
    this.active = false,
  });

  final IconData icon;
  final String tooltip;
  final VoidCallback onTap;
  final bool active;

  @override
  Widget build(BuildContext context) {
    final color = active ? _RideColors.orange : Colors.white.withOpacity(0.72);
    return Tooltip(
      message: tooltip,
      child: InkWell(
        borderRadius: BorderRadius.circular(17),
        onTap: onTap,
        child: SizedBox(
          width: 34,
          height: 34,
          child: Icon(icon, color: color, size: 21),
        ),
      ),
    );
  }
}

class _RouteBadge extends StatelessWidget {
  const _RouteBadge({
    required this.label,
    required this.color,
  });

  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withOpacity(0.09),
        borderRadius: BorderRadius.circular(5),
        border: Border.all(color: color),
      ),
      child: Text(
        label,
        style: TextStyle(
          color: color,
          fontSize: 12,
          fontWeight: FontWeight.w900,
        ),
      ),
    );
  }
}

class _RouteMetric extends StatelessWidget {
  const _RouteMetric({
    required this.value,
    required this.unit,
  });

  final String value;
  final String unit;

  @override
  Widget build(BuildContext context) {
    return RichText(
      text: TextSpan(
        children: [
          TextSpan(
            text: value,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 18,
              fontWeight: FontWeight.w900,
            ),
          ),
          if (unit.isNotEmpty)
            TextSpan(
              text: ' $unit',
              style: TextStyle(
                color: Colors.white.withOpacity(0.62),
                fontSize: 12,
                fontWeight: FontWeight.w700,
              ),
            ),
        ],
      ),
    );
  }
}

class _RouteDetailFavoriteButton extends StatefulWidget {
  const _RouteDetailFavoriteButton({
    required this.initialFavorited,
    required this.title,
    this.onToggle,
  });

  final bool initialFavorited;
  final String title;
  final VoidCallback? onToggle;

  @override
  State<_RouteDetailFavoriteButton> createState() =>
      _RouteDetailFavoriteButtonState();
}

class _RouteDetailFavoriteButtonState extends State<_RouteDetailFavoriteButton> {
  late bool _favorited;

  @override
  void initState() {
    super.initState();
    _favorited = widget.initialFavorited;
  }

  void _toggle() {
    setState(() => _favorited = !_favorited);
    widget.onToggle?.call();
    _showUiMessage(
      '收藏',
      _favorited ? '已收藏 ${widget.title}' : '已取消收藏 ${widget.title}',
    );
  }

  @override
  Widget build(BuildContext context) {
    return IconButton(
      onPressed: _toggle,
      icon: Icon(
        _favorited ? Icons.star : Icons.star_border,
        color: _favorited ? _RideColors.orange : Colors.white.withOpacity(0.9),
      ),
    );
  }
}

class _DetailTopBar extends StatelessWidget {
  const _DetailTopBar({required this.title, this.actions = const []});

  final String title;
  final List<Widget> actions;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(2, 6, 8, 4),
      child: Row(
        children: [
          IconButton(
            onPressed: () => Get.back<void>(),
            icon: const Icon(Icons.chevron_left, color: Colors.white, size: 30),
          ),
          Expanded(
            child: Text(
              title,
              textAlign: TextAlign.center,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 19,
                fontWeight: FontWeight.w900,
              ),
            ),
          ),
          if (actions.isEmpty) const SizedBox(width: 48) else ...actions,
        ],
      ),
    );
  }
}

class _DetailInfoRow extends StatelessWidget {
  const _DetailInfoRow({
    required this.label,
    required this.value,
    this.last = false,
  });

  final String label;
  final String value;
  final bool last;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 13),
      decoration: BoxDecoration(
        border: last
            ? null
            : Border(bottom: BorderSide(color: Colors.white.withOpacity(0.07))),
      ),
      child: Row(
        children: [
          Text(
            label,
            style: TextStyle(
              color: Colors.white.withOpacity(0.6),
              fontSize: 14,
              fontWeight: FontWeight.w700,
            ),
          ),
          const Spacer(),
          Text(
            value,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 14,
              fontWeight: FontWeight.w800,
            ),
          ),
        ],
      ),
    );
  }
}

class _RideRouteDetailPage extends StatelessWidget {
  const _RideRouteDetailPage({
    required this.title,
    required this.date,
    required this.distance,
    required this.climb,
    required this.duration,
    required this.difficulty,
    required this.difficultyColor,
    required this.variant,
    this.track = const <_GpxPoint>[],
    this.favorited = false,
    this.onFavoriteToggle,
  });

  final String title;
  final String date;
  final String distance;
  final String climb;
  final String duration;
  final String difficulty;
  final Color difficultyColor;
  final int variant;
  final List<_GpxPoint> track;
  final bool favorited;
  final VoidCallback? onFavoriteToggle;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _RideColors.background,
      body: SafeArea(
        bottom: false,
        child: Column(
          children: [
            _DetailTopBar(
              title: '路线详情',
              actions: [
                _RouteDetailFavoriteButton(
                  initialFavorited: favorited,
                  onToggle: onFavoriteToggle,
                  title: title,
                ),
                IconButton(
                  onPressed: () => _showUiMessage('更多', '更多操作入口已激活'),
                  icon: Icon(Icons.more_horiz, color: Colors.white.withOpacity(0.9)),
                ),
              ],
            ),
            Expanded(
              child: SingleChildScrollView(
                physics: const BouncingScrollPhysics(),
                padding: const EdgeInsets.fromLTRB(18, 4, 18, 18),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _GlassPanel(
                      padding: EdgeInsets.zero,
                      child: SizedBox(
                        height: 230,
                        child: Stack(
                          children: [
                            Positioned.fill(
                              child: ClipRRect(
                                borderRadius: BorderRadius.circular(15),
                                child: CustomPaint(
                                  painter: _RouteMapPainter(
                                    variant: variant,
                                    gpxTrack: track,
                                  ),
                                  child: const SizedBox.expand(),
                                ),
                              ),
                            ),
                            Positioned(
                              right: 10,
                              top: 10,
                              child: _RoundIconButton(
                                icon: Icons.fullscreen,
                                onTap: () => _openRidePage(
                                  () => _RideFullscreenMapPage(
                                    title: title,
                                    date: date,
                                    distance: distance,
                                    climb: climb,
                                    duration: duration,
                                    variant: variant,
                                    gpxTrack: track,
                                  ),
                                ),
                              ),
                            ),
                            Positioned(
                              right: 10,
                              bottom: 10,
                              child: _RoundIconButton(
                                icon: Icons.share_outlined,
                                onTap: () => _shareRouteSummary(
                                  context,
                                  title: title,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(height: 16),
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            title,
                            style: const TextStyle(
                              color: Colors.white,
                              fontSize: 22,
                              fontWeight: FontWeight.w900,
                            ),
                          ),
                        ),
                        Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 9, vertical: 4),
                          decoration: BoxDecoration(
                            color: const Color(0xFF3BE23E).withOpacity(0.12),
                            borderRadius: BorderRadius.circular(6),
                            border: Border.all(color: const Color(0xFF3BE23E)),
                          ),
                          child: const Text(
                            '公开',
                            style: TextStyle(
                              color: Color(0xFF3BE23E),
                              fontSize: 12,
                              fontWeight: FontWeight.w900,
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 6),
                    Text(
                      date,
                      style: TextStyle(
                        color: Colors.white.withOpacity(0.6),
                        fontSize: 14,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 16),
                    Row(
                      children: [
                        _RouteMetric(value: distance, unit: 'km'),
                        const SizedBox(width: 34),
                        _RouteMetric(value: climb, unit: 'm'),
                        const SizedBox(width: 34),
                        _RouteMetric(value: duration, unit: ''),
                      ],
                    ),
                    const SizedBox(height: 14),
                    Row(
                      children: [
                        _RouteBadge(label: '公路', color: _RideColors.orange),
                        const SizedBox(width: 8),
                        _RouteBadge(
                            label: '难度 $difficulty', color: difficultyColor),
                      ],
                    ),
                    const SizedBox(height: 16),
                    _GlassPanel(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            '路线简介',
                            style: TextStyle(
                              color: Colors.white,
                              fontSize: 18,
                              fontWeight: FontWeight.w900,
                            ),
                          ),
                          const SizedBox(height: 8),
                          Text(
                            track.isEmpty
                                ? '这是一条经典的环山路线，适合有一定经验的骑友。路线包含平路、爬坡与下坡，沿途风景优美，建议早晨出发，注意补给和防晒。'
                                : '已解析导入路书中的 ${track.length} 个路线点，地图与海拔图会按 GPX 轨迹绘制。请在发送到设备前确认路线方向与路点完整性。',
                            style: TextStyle(
                              color: Colors.white.withOpacity(0.68),
                              fontSize: 14,
                              height: 1.5,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 12),
                    _GlassPanel(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              const Text(
                                '海拔图',
                                style: TextStyle(
                                  color: Colors.white,
                                  fontSize: 18,
                                  fontWeight: FontWeight.w900,
                                ),
                              ),
                              const Spacer(),
                              Text(
                                '累计爬升 $climb m',
                                style: const TextStyle(
                                  color: Color(0xFFA533FF),
                                  fontSize: 13,
                                  fontWeight: FontWeight.w800,
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 12),
                          SizedBox(
                            height: 120,
                            child: _InteractiveElevationChart(
                              values: _routeElevationValues(track),
                              color: const Color(0xFFA533FF),
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 12),
                    _GlassPanel(
                      child: Column(
                        children: [
                          _DetailInfoRow(
                            label: '起点',
                            value: _routePointLabel(
                              track.isEmpty ? null : track.first,
                            ),
                          ),
                          _DetailInfoRow(
                            label: '终点',
                            value: _routePointLabel(
                              track.isEmpty ? null : track.last,
                            ),
                          ),
                          _DetailInfoRow(
                            label: '最高海拔',
                            value: _routeMaxElevationLabel(track),
                            last: true,
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
            // 底部固定操作栏
            Container(
              padding: const EdgeInsets.fromLTRB(18, 10, 18, 10),
              decoration: BoxDecoration(
                color: const Color(0xFF101720),
                border: Border(
                  top: BorderSide(color: Colors.white.withOpacity(0.08)),
                ),
              ),
              child: SafeArea(
                top: false,
                child: Row(
                  children: [
                    Expanded(
                      child: OutlinedButton(
                        onPressed: () => _showUiMessage('发送到设备', '已发送路线到设备'),
                        style: OutlinedButton.styleFrom(
                          foregroundColor: Colors.white,
                          minimumSize: const Size(0, 50),
                          side: BorderSide(color: Colors.white.withOpacity(0.25)),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(14),
                          ),
                        ),
                        child: const Text(
                          '发送到设备',
                          style: TextStyle(
                              fontSize: 16, fontWeight: FontWeight.w900),
                        ),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: ElevatedButton(
                        onPressed: () => _showUiMessage('导航', '开始导航'),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: _RideColors.orange,
                          foregroundColor: Colors.white,
                          minimumSize: const Size(0, 50),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(14),
                          ),
                        ),
                        child: const Text(
                          '导航',
                          style: TextStyle(
                              fontSize: 16, fontWeight: FontWeight.w900),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _RideFullscreenMapPage extends StatelessWidget {
  const _RideFullscreenMapPage({
    required this.title,
    required this.date,
    required this.distance,
    required this.climb,
    required this.duration,
    required this.variant,
    this.track = const <RidePoint>[],
    this.gpxTrack = const <_GpxPoint>[],
  });

  final String title;
  final String date;
  final String distance;
  final String climb;
  final String duration;
  final int variant;
  final List<RidePoint> track;
  final List<_GpxPoint> gpxTrack;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _RideColors.background,
      body: SafeArea(
        bottom: false,
        child: Column(
          children: [
            _DetailTopBar(
              title: '地图全屏',
              actions: [
                IconButton(
                  onPressed: () => _shareRouteSummary(context, title: title),
                  icon: Icon(
                    Icons.share_outlined,
                    color: Colors.white.withOpacity(0.9),
                  ),
                ),
              ],
            ),
            Expanded(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(18, 4, 18, 18),
                child: Stack(
                  children: [
                    Positioned.fill(
                      child: _GlassPanel(
                        padding: EdgeInsets.zero,
                        child: ClipRRect(
                          borderRadius: BorderRadius.circular(15),
                          child: CustomPaint(
                            painter: _RouteMapPainter(
                              variant: variant,
                              track: track,
                              gpxTrack: gpxTrack,
                            ),
                            child: const SizedBox.expand(),
                          ),
                        ),
                      ),
                    ),
                    Positioned(
                      left: 16,
                      right: 16,
                      top: 16,
                      child: _MapHeaderOverlay(title: title, date: date),
                    ),
                    Positioned(
                      left: 16,
                      right: 16,
                      bottom: 16,
                      child: _MapStatsOverlay(
                        distance: distance,
                        climb: climb,
                        duration: duration,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _MapHeaderOverlay extends StatelessWidget {
  const _MapHeaderOverlay({
    required this.title,
    required this.date,
  });

  final String title;
  final String date;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: const Color(0xFF101720).withOpacity(0.74),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.white.withOpacity(0.10)),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        child: Row(
          children: [
            Container(
              width: 34,
              height: 34,
              decoration: BoxDecoration(
                color: _RideColors.orange.withOpacity(0.16),
                borderRadius: BorderRadius.circular(12),
              ),
              child: const Icon(
                Icons.directions_bike,
                color: _RideColors.orange,
                size: 19,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    title,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 17,
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                  const SizedBox(height: 3),
                  Text(
                    date,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      color: Colors.white.withOpacity(0.62),
                      fontSize: 12,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _MapStatsOverlay extends StatelessWidget {
  const _MapStatsOverlay({
    required this.distance,
    required this.climb,
    required this.duration,
  });

  final String distance;
  final String climb;
  final String duration;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: const Color(0xFF101720).withOpacity(0.78),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.white.withOpacity(0.10)),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
        child: Row(
          children: [
            _MapStatItem(label: '距离', value: distance, unit: 'km'),
            const _MapStatDivider(),
            _MapStatItem(label: '爬升', value: climb, unit: 'm'),
            const _MapStatDivider(),
            _MapStatItem(label: '用时', value: duration, unit: ''),
          ],
        ),
      ),
    );
  }
}

class _MapStatItem extends StatelessWidget {
  const _MapStatItem({
    required this.label,
    required this.value,
    required this.unit,
  });

  final String label;
  final String value;
  final String unit;

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            label,
            style: TextStyle(
              color: Colors.white.withOpacity(0.50),
              fontSize: 11,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 4),
          RichText(
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            text: TextSpan(
              children: [
                TextSpan(
                  text: value,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 16,
                    fontWeight: FontWeight.w900,
                  ),
                ),
                if (unit.isNotEmpty)
                  TextSpan(
                    text: ' $unit',
                    style: TextStyle(
                      color: Colors.white.withOpacity(0.62),
                      fontSize: 11,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _MapStatDivider extends StatelessWidget {
  const _MapStatDivider();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 1,
      height: 34,
      color: Colors.white.withOpacity(0.10),
    );
  }
}

class _DevicesPage extends StatefulWidget {
  const _DevicesPage({required this.controller});

  final RideController controller;

  @override
  State<_DevicesPage> createState() => _DevicesPageState();
}

class _DevicesPageState extends State<_DevicesPage>
    with SingleTickerProviderStateMixin {
  late final AnimationController _radar;
  bool _scanning = true;

  @override
  void initState() {
    super.initState();
    // 雷达扫描旋转动画（纯本地视觉状态，不接真实 BleController）。
    _radar = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1600),
    )..repeat();
  }

  @override
  void dispose() {
    _radar.dispose();
    super.dispose();
  }

  void _toggleScan() {
    setState(() {
      _scanning = !_scanning;
      if (_scanning) {
        _radar.repeat();
      } else {
        _radar.stop();
      }
    });
    _showUiMessage(
      _scanning ? '开始扫描' : '停止扫描',
      _scanning ? '正在扫描附近设备...' : '已停止扫描',
    );
  }

  void _refreshDevices() {
    if (!_scanning) {
      setState(() {
        _scanning = true;
        _radar.repeat();
      });
    }
    _showUiMessage('刷新设备', '正在重新扫描可用设备...');
  }

  void _openMissingDeviceHelp() {
    unawaited(
      _showMissingDeviceActions(
        context,
        onRefresh: _refreshDevices,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        // 固定子头：扫描雷达 + 停止扫描（本地视觉状态，不接真实 BleController）
        Padding(
          padding: const EdgeInsets.fromLTRB(18, 12, 18, 0),
          child: _ScanPanel(
            scanning: _scanning,
            rotation: _radar,
            onToggle: _toggleScan,
          ),
        ),
        const SizedBox(height: 12),
        // 单一滚动区：可用设备列表
        Expanded(
          child: SingleChildScrollView(
            physics: const BouncingScrollPhysics(),
            padding: const EdgeInsets.fromLTRB(18, 0, 18, 16),
            child: _AvailableDevicesPanel(
              onRefresh: _refreshDevices,
              onMissingDevice: _openMissingDeviceHelp,
            ),
          ),
        ),
      ],
    );
  }
}

class _ScanPanel extends StatelessWidget {
  const _ScanPanel({
    required this.scanning,
    required this.rotation,
    required this.onToggle,
  });

  final bool scanning;
  final Animation<double> rotation;
  final VoidCallback onToggle;

  @override
  Widget build(BuildContext context) {
    return _GlassPanel(
      padding: const EdgeInsets.fromLTRB(18, 14, 18, 12),
      child: Column(
        children: [
          Text(
            scanning ? '正在扫描设备...' : '扫描已停止',
            style: const TextStyle(
              color: Colors.white,
              fontSize: 18,
              fontWeight: FontWeight.w900,
            ),
          ),
          const SizedBox(height: 5),
          Text(
            scanning ? '请确保设备已开机并靠近手机' : '点按下方按钮重新开始扫描',
            style: TextStyle(
              color: Colors.white.withOpacity(0.66),
              fontSize: 13,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 12),
          SizedBox(
            height: 104,
            child: AnimatedBuilder(
              animation: rotation,
              builder: (context, child) {
                return CustomPaint(
                  painter: _RadarPainter(
                    sweepStart: rotation.value * 2 * math.pi,
                    active: scanning,
                  ),
                  child: child,
                );
              },
              child: Center(
                child: Container(
                  width: 40,
                  height: 40,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: const Color(0xFF3BE23E).withOpacity(0.18),
                  ),
                  child: const Icon(
                    Icons.bluetooth,
                    color: Color(0xFF3BE23E),
                    size: 22,
                  ),
                ),
              ),
            ),
          ),
          const SizedBox(height: 10),
          OutlinedButton(
            onPressed: onToggle,
            style: OutlinedButton.styleFrom(
              foregroundColor: _RideColors.orange,
              side: BorderSide(color: Colors.white.withOpacity(0.14)),
              minimumSize: const Size(200, 44),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(22),
              ),
            ),
            child: Text(
              scanning ? '停止扫描' : '扫描设备',
              style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w900),
            ),
          ),
        ],
      ),
    );
  }
}

class _AvailableDevicesPanel extends StatelessWidget {
  const _AvailableDevicesPanel({
    required this.onRefresh,
    required this.onMissingDevice,
  });

  final VoidCallback onRefresh;
  final VoidCallback onMissingDevice;

  @override
  Widget build(BuildContext context) {
    return _GlassPanel(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 14),
      child: Column(
        children: [
          Row(
            children: [
              const Text(
                '可用设备',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 20,
                  fontWeight: FontWeight.w900,
                ),
              ),
              const Spacer(),
              IconButton(
                onPressed: onRefresh,
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(),
                icon: Icon(Icons.refresh, color: Colors.white.withOpacity(0.78)),
              ),
            ],
          ),
          const SizedBox(height: 14),
          _DeviceRow(
            title: 'iGPSPORT BSC300_1234',
            type: '码表',
            bars: 4,
            onTap: () => _openRidePage(
              () => const _RideDeviceDetailPage(
                name: 'iGPSPORT BSC300_1234',
                type: '码表',
              ),
            ),
          ),
          const SizedBox(height: 10),
          _DeviceRow(
            title: 'iGPSPORT SR30_5678',
            type: '雷达',
            bars: 4,
            onTap: () => _openRidePage(
              () => const _RideDeviceDetailPage(
                name: 'iGPSPORT SR30_5678',
                type: '雷达',
              ),
            ),
          ),
          const SizedBox(height: 10),
          _DeviceRow(
            title: 'iGPSPORT HR40_9012',
            type: '心率带',
            bars: 3,
            onTap: () => _openRidePage(
              () => const _RideDeviceDetailPage(
                name: 'iGPSPORT HR40_9012',
                type: '心率带',
              ),
            ),
          ),
          const SizedBox(height: 18),
          InkWell(
            borderRadius: BorderRadius.circular(12),
            onTap: onMissingDevice,
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 10),
              child: Row(
                children: [
                  Text(
                    '未找到我的设备',
                    style: TextStyle(
                      color: Colors.white.withOpacity(0.68),
                      fontSize: 15,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  const Spacer(),
                  Icon(
                    Icons.chevron_right,
                    color: Colors.white.withOpacity(0.82),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _DeviceRow extends StatelessWidget {
  const _DeviceRow({
    required this.title,
    required this.type,
    required this.bars,
    this.onTap,
  });

  final String title;
  final String type;
  final int bars;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: onTap,
      child: Container(
        height: 82,
        padding: const EdgeInsets.symmetric(horizontal: 12),
        decoration: BoxDecoration(
          color: Colors.white.withOpacity(0.035),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: Colors.white.withOpacity(0.07)),
        ),
        child: Row(
          children: [
            _DeviceThumbnail(kind: type, compact: true),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 16,
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                  const SizedBox(height: 6),
                  Align(
                    alignment: Alignment.centerLeft,
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 7, vertical: 2),
                      decoration: BoxDecoration(
                        borderRadius: BorderRadius.circular(4),
                        border:
                            Border.all(color: Colors.white.withOpacity(0.18)),
                      ),
                      child: Text(
                        type,
                        style: TextStyle(
                          color: Colors.white.withOpacity(0.78),
                          fontSize: 12,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
            _SignalBars(value: bars),
            const SizedBox(width: 16),
            OutlinedButton(
              onPressed:
                  onTap ?? () => _showUiMessage('连接设备', '$title 正在连接...'),
              style: OutlinedButton.styleFrom(
                foregroundColor: _RideColors.orange,
                side: const BorderSide(color: _RideColors.orange),
                minimumSize: const Size(76, 38),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(20),
                ),
              ),
              child: const Text(
                '连接',
                style: TextStyle(fontWeight: FontWeight.w900),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _DeviceThumbnail extends StatelessWidget {
  const _DeviceThumbnail({
    required this.kind,
    this.compact = false,
  });

  final String kind;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    if (kind == '雷达') return _RadarDeviceThumbnail(compact: compact);
    if (kind == '心率带') return _HeartRateDeviceThumbnail(compact: compact);
    return _ComputerDeviceThumbnail(compact: compact);
  }
}

class _ComputerDeviceThumbnail extends StatelessWidget {
  const _ComputerDeviceThumbnail({required this.compact});

  final bool compact;

  @override
  Widget build(BuildContext context) {
    final width = compact ? 50.0 : 84.0;
    final height = compact ? 62.0 : 104.0;
    final screenInset = compact ? 7.0 : 12.0;
    return SizedBox(
      width: compact ? 56 : 92,
      height: compact ? 64 : 108,
      child: Center(
        child: Container(
          width: width,
          height: height,
          padding: EdgeInsets.all(screenInset),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(compact ? 10 : 16),
            gradient: const LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [Color(0xFF30343A), Color(0xFF101318)],
            ),
            border: Border.all(color: Colors.white.withOpacity(0.16)),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withOpacity(0.34),
                blurRadius: compact ? 10 : 18,
                offset: const Offset(0, 8),
              ),
            ],
          ),
          child: Container(
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(compact ? 6 : 10),
              color: const Color(0xFF1B2026),
              border: Border.all(color: Colors.white.withOpacity(0.08)),
            ),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(
                  'iGPS',
                  style: TextStyle(
                    color: Colors.white.withOpacity(0.86),
                    fontSize: compact ? 5 : 9,
                    fontWeight: FontWeight.w900,
                    letterSpacing: 0.2,
                  ),
                ),
                SizedBox(height: compact ? 3 : 6),
                for (var i = 0; i < 3; i++)
                  Padding(
                    padding: EdgeInsets.only(bottom: compact ? 2 : 4),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        _DeviceScreenLine(width: compact ? 13 : 22),
                        SizedBox(width: compact ? 3 : 5),
                        _DeviceScreenLine(width: compact ? 8 : 15),
                      ],
                    ),
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _RadarDeviceThumbnail extends StatelessWidget {
  const _RadarDeviceThumbnail({required this.compact});

  final bool compact;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: compact ? 56 : 92,
      height: compact ? 64 : 108,
      child: Center(
        child: Container(
          width: compact ? 42 : 68,
          height: compact ? 58 : 92,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(999),
            gradient: const LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [Color(0xFF2E3338), Color(0xFF101318)],
            ),
            border: Border.all(color: Colors.white.withOpacity(0.14)),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withOpacity(0.34),
                blurRadius: compact ? 10 : 18,
                offset: const Offset(0, 8),
              ),
            ],
          ),
          child: Center(
            child: Container(
              width: compact ? 18 : 30,
              height: compact ? 18 : 30,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: Colors.white.withOpacity(0.05),
                border: Border.all(color: Colors.white.withOpacity(0.18)),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _HeartRateDeviceThumbnail extends StatelessWidget {
  const _HeartRateDeviceThumbnail({required this.compact});

  final bool compact;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: compact ? 56 : 92,
      height: compact ? 64 : 108,
      child: Center(
        child: Stack(
          alignment: Alignment.center,
          children: [
            Container(
              width: compact ? 54 : 88,
              height: compact ? 16 : 26,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(999),
                gradient: const LinearGradient(
                  colors: [Color(0xFF14171C), Color(0xFF2B3036), Color(0xFF14171C)],
                ),
              ),
            ),
            Container(
              width: compact ? 34 : 54,
              height: compact ? 24 : 38,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(compact ? 7 : 11),
                gradient: const LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: [Color(0xFF282D32), Color(0xFF0F1216)],
                ),
                border: Border.all(color: Colors.white.withOpacity(0.12)),
              ),
              child: Center(
                child: Text(
                  'iGPS',
                  style: TextStyle(
                    color: Colors.white.withOpacity(0.78),
                    fontSize: compact ? 5 : 8,
                    fontWeight: FontWeight.w900,
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _DeviceScreenLine extends StatelessWidget {
  const _DeviceScreenLine({required this.width});

  final double width;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: width,
      height: 2,
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.76),
        borderRadius: BorderRadius.circular(999),
      ),
    );
  }
}

class _ConnectedDevicePanel extends StatelessWidget {
  const _ConnectedDevicePanel({
    this.deviceName = 'iGPSPORT BSC300_1234',
    this.deviceType = '码表',
  });

  final String deviceName;
  final String deviceType;

  @override
  Widget build(BuildContext context) {
    return _GlassPanel(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              _DeviceThumbnail(kind: deviceType),
              const SizedBox(width: 18),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      deviceName,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 20,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                    const SizedBox(height: 10),
                    Row(
                      children: [
                        Container(
                          width: 10,
                          height: 10,
                          decoration: const BoxDecoration(
                            color: Color(0xFF3BE23E),
                            shape: BoxShape.circle,
                          ),
                        ),
                        const SizedBox(width: 8),
                        Text(
                          '已连接',
                          style: TextStyle(
                            color: Colors.white.withOpacity(0.76),
                            fontSize: 15,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    Text(
                      '固件版本：v1.23.0',
                      style: TextStyle(
                        color: Colors.white.withOpacity(0.66),
                        fontSize: 14,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 6),
                    Text(
                      '电量：100%',
                      style: TextStyle(
                        color: Colors.white.withOpacity(0.66),
                        fontSize: 14,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 18),
          const _DeviceFirmwareUpdateRow(),
          const SizedBox(height: 6),
          const _DeviceSettingRow(
            icon: Icons.settings,
            color: Color(0xFF268DFF),
            title: '设备设置',
          ),
          const _DeviceSettingRow(
            icon: Icons.grid_view,
            color: Color(0xFF4AD14A),
            title: '页面配置',
          ),
          const _DeviceSettingRow(
            icon: Icons.link,
            color: Color(0xFFA533FF),
            title: '传感器管理',
          ),
          const _DeviceSwitchRow(
            icon: Icons.pause,
            color: _RideColors.orange,
            title: '自动暂停',
            subtitle: '停止运动时自动暂停记录',
          ),
          const _DeviceSwitchRow(
            icon: Icons.trip_origin,
            color: Color(0xFFFFC400),
            title: '自动计圈',
            subtitle: '按距离自动生成计圈',
          ),
        ],
      ),
    );
  }
}

class _DeviceInfoPanel extends StatelessWidget {
  const _DeviceInfoPanel({required this.name});

  final String name;

  @override
  Widget build(BuildContext context) {
    return _GlassPanel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            '设备信息',
            style: TextStyle(
              color: Colors.white,
              fontSize: 18,
              fontWeight: FontWeight.w900,
            ),
          ),
          const SizedBox(height: 4),
          _DetailInfoRow(label: '设备名称', value: name),
          const _DetailInfoRow(label: '序列号', value: 'SN1234567890'),
          const _DetailInfoRow(label: '固件版本', value: 'v1.23.0'),
          const _DetailInfoRow(label: '硬件版本', value: 'v1.0'),
          const _DetailInfoRow(
              label: 'MAC 地址', value: 'D0:55:3C:12:34:56', last: true),
        ],
      ),
    );
  }
}

class _RideDeviceDetailPage extends StatelessWidget {
  const _RideDeviceDetailPage({required this.name, required this.type});

  final String name;
  final String type;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _RideColors.background,
      body: SafeArea(
        bottom: false,
        child: Column(
          children: [
            _DetailTopBar(
              title: '设备',
              actions: [
                IconButton(
                  onPressed: () => _showUiMessage('更多', '更多操作入口已激活'),
                  icon:
                      Icon(Icons.more_horiz, color: Colors.white.withOpacity(0.9)),
                ),
              ],
            ),
            Expanded(
              child: SingleChildScrollView(
                physics: const BouncingScrollPhysics(),
                padding: const EdgeInsets.fromLTRB(18, 4, 18, 18),
                child: Column(
                  children: [
                    _ConnectedDevicePanel(deviceName: name, deviceType: type),
                    const SizedBox(height: 12),
                    _DeviceInfoPanel(name: name),
                    const SizedBox(height: 14),
                    OutlinedButton(
                      onPressed: () => _showUiMessage('解除绑定', '已打开设备解绑确认'),
                      style: OutlinedButton.styleFrom(
                        foregroundColor: _RideColors.orange,
                        minimumSize: const Size(double.infinity, 52),
                        side: BorderSide(color: Colors.white.withOpacity(0.12)),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(14),
                        ),
                      ),
                      child: const Text(
                        '解除绑定',
                        style:
                            TextStyle(fontSize: 16, fontWeight: FontWeight.w900),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _DeviceFirmwareUpdateRow extends StatelessWidget {
  const _DeviceFirmwareUpdateRow();

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        borderRadius: BorderRadius.circular(18),
        onTap: () => Get.to(() => const OtaUpgradePage()),
        child: Ink(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            gradient: LinearGradient(
              colors: [
                const Color(0xFF1C8CFF).withOpacity(0.34),
                const Color(0xFF55E8E6).withOpacity(0.18),
              ],
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
            ),
            borderRadius: BorderRadius.circular(18),
            border: Border.all(color: Colors.white.withOpacity(0.13)),
          ),
          child: Row(
            children: [
              Container(
                width: 42,
                height: 42,
                decoration: BoxDecoration(
                  color: Colors.white.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(14),
                  border: Border.all(
                    color: const Color(0xFF55E8E6).withOpacity(0.5),
                  ),
                ),
                child: const Icon(
                  Icons.system_update_alt,
                  color: Color(0xFF55E8E6),
                  size: 22,
                ),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      '检查单片机固件更新',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 16,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      '下载最新码表固件',
                      style: TextStyle(
                        color: Colors.white.withOpacity(0.62),
                        fontSize: 13,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 12),
              Icon(
                Icons.chevron_right,
                color: Colors.white.withOpacity(0.78),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _DeviceSettingRow extends StatelessWidget {
  const _DeviceSettingRow({
    required this.icon,
    required this.color,
    required this.title,
  });

  final IconData icon;
  final Color color;
  final String title;

  @override
  Widget build(BuildContext context) {
    return _DeviceRowBase(
      icon: icon,
      color: color,
      title: title,
      trailing: Icon(Icons.chevron_right, color: Colors.white.withOpacity(0.76)),
    );
  }
}

class _DeviceSwitchRow extends StatelessWidget {
  const _DeviceSwitchRow({
    required this.icon,
    required this.color,
    required this.title,
    required this.subtitle,
  });

  final IconData icon;
  final Color color;
  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) {
    return _DeviceRowBase(
      icon: icon,
      color: color,
      title: title,
      subtitle: subtitle,
      trailing: Switch(
        value: true,
        onChanged: (_) {},
        activeColor: Colors.white,
        activeTrackColor: _RideColors.orange,
      ),
    );
  }
}

class _DeviceRowBase extends StatelessWidget {
  const _DeviceRowBase({
    required this.icon,
    required this.color,
    required this.title,
    required this.trailing,
    this.subtitle,
  });

  final IconData icon;
  final Color color;
  final String title;
  final String? subtitle;
  final Widget trailing;

  @override
  Widget build(BuildContext context) {
    return ConstrainedBox(
      constraints: const BoxConstraints(minHeight: 70),
      child: Container(
        decoration: BoxDecoration(
          border: Border(
            bottom: BorderSide(color: Colors.white.withOpacity(0.08)),
          ),
        ),
        child: Row(
          children: [
            Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                color: color.withOpacity(0.11),
                shape: BoxShape.circle,
                border: Border.all(color: color, width: 2),
              ),
              child: Icon(icon, color: color, size: 21),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 17,
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                  if (subtitle != null) ...[
                    const SizedBox(height: 4),
                    Text(
                      subtitle!,
                      style: TextStyle(
                        color: Colors.white.withOpacity(0.56),
                        fontSize: 13,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ],
                ],
              ),
            ),
            trailing,
          ],
        ),
      ),
    );
  }
}

class _SignalBars extends StatelessWidget {
  const _SignalBars({required this.value});

  final int value;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 28,
      height: 28,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          for (var i = 0; i < 4; i++)
            Container(
              width: 4,
              height: 8.0 + i * 5,
              decoration: BoxDecoration(
                color: i < value
                    ? const Color(0xFF55E8E6)
                    : Colors.white.withOpacity(0.18),
                borderRadius: BorderRadius.circular(999),
              ),
            ),
        ],
      ),
    );
  }
}

class _RecordingBar extends StatelessWidget {
  const _RecordingBar({required this.controller});

  final RideController controller;

  Future<void> _confirmFinish(BuildContext context) async {
    final confirmed = await showDialog<bool>(
      context: context,
      barrierDismissible: true,
      builder: (dialogContext) {
        return AlertDialog(
          backgroundColor: const Color(0xFF121922),
          surfaceTintColor: Colors.transparent,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(18),
            side: BorderSide(color: Colors.white.withOpacity(0.10)),
          ),
          title: const Text(
            '结束骑行',
            style: TextStyle(
              color: Colors.white,
              fontWeight: FontWeight.w900,
            ),
          ),
          content: Text(
            '确定结束并保存本次骑行吗？',
            style: TextStyle(
              color: Colors.white.withOpacity(0.72),
              fontWeight: FontWeight.w700,
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(dialogContext).pop(false),
              child: Text(
                '继续骑行',
                style: TextStyle(
                  color: Colors.white.withOpacity(0.72),
                  fontWeight: FontWeight.w900,
                ),
              ),
            ),
            ElevatedButton(
              onPressed: () => Navigator.of(dialogContext).pop(true),
              style: ElevatedButton.styleFrom(
                backgroundColor: _RideColors.orange,
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
              child: const Text(
                '结束并保存',
                style: TextStyle(fontWeight: FontWeight.w900),
              ),
            ),
          ],
        );
      },
    );

    if (confirmed == true) {
      await controller.saveCurrentRide();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Obx(() {
      final paused = controller.isPaused.value;
      final elapsed = controller.elapsed.value;
      return Container(
        padding: const EdgeInsets.fromLTRB(18, 8, 10, 8),
        decoration: BoxDecoration(
          color: const Color(0xFF12181F),
          border: Border(
            top: BorderSide(color: Colors.white.withOpacity(0.06)),
          ),
        ),
        child: Row(
          children: [
            Container(
              width: 9,
              height: 9,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: paused
                    ? const Color(0xFFFFC400)
                    : const Color(0xFF3BE23E),
              ),
            ),
            const SizedBox(width: 8),
            Text(
              paused ? '已暂停' : '记录中',
              style: TextStyle(
                color: Colors.white.withOpacity(0.86),
                fontSize: 14,
                fontWeight: FontWeight.w800,
              ),
            ),
            const SizedBox(width: 10),
            Text(
              _formatDuration(elapsed),
              style: const TextStyle(
                color: Colors.white,
                fontSize: 15,
                fontWeight: FontWeight.w900,
              ),
            ),
            const Spacer(),
            TextButton.icon(
              onPressed: () => unawaited(_confirmFinish(context)),
              style: TextButton.styleFrom(
                foregroundColor: _RideColors.orange,
                textStyle: const TextStyle(fontWeight: FontWeight.w900),
              ),
              icon: const Icon(Icons.stop_circle, size: 20),
              label: const Text('结束并保存'),
            ),
          ],
        ),
      );
    });
  }
}

class _RideTabBar extends StatelessWidget {
  const _RideTabBar({
    required this.controller,
    required this.onSelect,
  });

  final RideController controller;
  final ValueChanged<int> onSelect;

  @override
  Widget build(BuildContext context) {
    return Obx(() {
      final selectedIndex = controller.activeTabIndex.value;
      final isRecording = controller.isRecording.value;
      final isPaused = controller.isPaused.value;
      return Container(
        decoration: BoxDecoration(
          color: const Color(0xFF101720).withOpacity(0.98),
          border: Border(
            top: BorderSide(color: Colors.white.withOpacity(0.08)),
          ),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withOpacity(0.40),
              blurRadius: 30,
              offset: const Offset(0, -12),
            ),
          ],
        ),
        child: SafeArea(
          top: false,
          child: SizedBox(
            height: 78,
            child: Row(
              children: [
                _BottomAction(
                  icon: Icons.speed,
                  label: '仪表盘',
                  selected: selectedIndex == 0,
                  onTap: () => onSelect(0),
                ),
                _BottomAction(
                  icon: Icons.bar_chart,
                  label: '统计',
                  selected: selectedIndex == 1,
                  onTap: () => onSelect(1),
                ),
                _BottomRecordAction(
                  isRecording: isRecording,
                  isPaused: isPaused,
                  onTap: () {
                    if (isRecording) {
                      controller.pauseResume();
                    } else {
                      controller.start();
                    }
                  },
                ),
                _BottomAction(
                  icon: Icons.explore,
                  label: '路线',
                  selected: selectedIndex == 2,
                  onTap: () => onSelect(2),
                ),
                _BottomAction(
                  icon: Icons.devices_other,
                  label: '设备',
                  selected: selectedIndex == 3,
                  onTap: () => onSelect(3),
                ),
              ],
            ),
          ),
        ),
      );
    });
  }
}

class _BottomRecordAction extends StatelessWidget {
  const _BottomRecordAction({
    required this.isRecording,
    required this.isPaused,
    required this.onTap,
  });

  final bool isRecording;
  final bool isPaused;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final icon = isRecording && !isPaused ? Icons.pause : Icons.play_arrow;
    return Expanded(
      child: InkWell(
        onTap: onTap,
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            AnimatedContainer(
              duration: const Duration(milliseconds: 180),
              width: 46,
              height: 46,
              decoration: BoxDecoration(
                color: _RideColors.orange,
                shape: BoxShape.circle,
                boxShadow: [
                  BoxShadow(
                    color: _RideColors.orange.withOpacity(0.36),
                    blurRadius: 20,
                    offset: const Offset(0, 8),
                  ),
                ],
              ),
              child: Icon(icon, color: Colors.white, size: 28),
            ),
            const SizedBox(height: 5),
            const Text(
              '开始/暂停',
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                color: _RideColors.orange,
                fontSize: 12,
                fontWeight: FontWeight.w900,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _BottomAction extends StatelessWidget {
  const _BottomAction({
    required this.icon,
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final IconData icon;
  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final color = selected ? _RideColors.orange : Colors.white.withOpacity(0.62);
    return Expanded(
      child: InkWell(
        onTap: onTap,
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            AnimatedContainer(
              duration: const Duration(milliseconds: 180),
              width: selected ? 42 : 36,
              height: selected ? 42 : 36,
              decoration: BoxDecoration(
                color: selected
                    ? _RideColors.orange.withOpacity(0.12)
                    : Colors.transparent,
                shape: BoxShape.circle,
                border: Border.all(
                  color: selected ? _RideColors.orange : color,
                  width: selected ? 2 : 1.7,
                ),
              ),
              child: Icon(icon, color: color, size: selected ? 23 : 21),
            ),
            const SizedBox(height: 6),
            Text(
              label,
              style: TextStyle(
                color: color,
                fontSize: 13,
                fontWeight: selected ? FontWeight.w900 : FontWeight.w700,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _OuterFrame extends StatelessWidget {
  const _OuterFrame({
    required this.child,
    this.padding = const EdgeInsets.all(10),
  });

  final Widget child;
  final EdgeInsetsGeometry padding;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: padding,
      decoration: BoxDecoration(
        color: const Color(0xFF151B24).withOpacity(0.82),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: Colors.white.withOpacity(0.08)),
      ),
      child: child,
    );
  }
}

class _GlassPanel extends StatelessWidget {
  const _GlassPanel({
    required this.child,
    this.padding = const EdgeInsets.all(14),
  });

  final Widget child;
  final EdgeInsetsGeometry padding;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: padding,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(15),
        border: Border.all(color: Colors.white.withOpacity(0.08)),
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            const Color(0xFF222A35).withOpacity(0.82),
            const Color(0xFF141A23).withOpacity(0.96),
          ],
        ),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.30),
            blurRadius: 22,
            offset: const Offset(0, 12),
          ),
        ],
      ),
      child: child,
    );
  }
}

class _RoundIconButton extends StatelessWidget {
  const _RoundIconButton({
    required this.icon,
    required this.onTap,
  });

  final IconData icon;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      customBorder: const CircleBorder(),
      child: Container(
        width: 44,
        height: 44,
        decoration: BoxDecoration(
          color: Colors.white.withOpacity(0.10),
          shape: BoxShape.circle,
        ),
        child: Icon(icon, color: Colors.white.withOpacity(0.82), size: 23),
      ),
    );
  }
}

class _HeroStat extends StatelessWidget {
  const _HeroStat({
    required this.label,
    required this.value,
    required this.unit,
  });

  final String label;
  final String value;
  final String unit;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(
          label,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: TextStyle(
            color: Colors.white.withOpacity(0.48),
            fontSize: 11,
            fontWeight: FontWeight.w700,
          ),
        ),
        const SizedBox(height: 3),
        RichText(
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          text: TextSpan(
            children: [
              TextSpan(
                text: value,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 15,
                  fontWeight: FontWeight.w900,
                ),
              ),
              if (unit.isNotEmpty)
                TextSpan(
                  text: ' $unit',
                  style: TextStyle(
                    color: unit == '高'
                        ? const Color(0xFFE34CFF)
                        : Colors.white.withOpacity(0.62),
                    fontSize: 10,
                    fontWeight: FontWeight.w800,
                  ),
                ),
            ],
          ),
        ),
      ],
    );
  }
}

class _LegendText extends StatelessWidget {
  const _LegendText({
    required this.label,
    required this.value,
    required this.color,
  });

  final String label;
  final String value;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Text(
          '$label ',
          style: TextStyle(
            color: Colors.white.withOpacity(0.54),
            fontSize: 13,
            fontWeight: FontWeight.w700,
          ),
        ),
        Text(
          value,
          style: TextStyle(
            color: color,
            fontSize: 13,
            fontWeight: FontWeight.w900,
          ),
        ),
      ],
    );
  }
}

class _RideSample {
  const _RideSample({
    required this.distanceText,
    required this.durationText,
    required this.avgSpeedText,
    required this.maxSpeedText,
    required this.climbText,
  });

  final String distanceText;
  final String durationText;
  final String avgSpeedText;
  final String maxSpeedText;
  final String climbText;

  factory _RideSample.from(RideController controller) {
    return _RideSample(
      distanceText: controller.distanceKm.value.toStringAsFixed(2),
      durationText: _formatDuration(controller.elapsed.value),
      avgSpeedText: controller.avgSpeedKmh.value.toStringAsFixed(1),
      maxSpeedText: controller.maxSpeedKmh.value.toStringAsFixed(1),
      climbText: controller.totalClimbM.value.toStringAsFixed(0),
    );
  }
}

class _RideStats {
  const _RideStats({
    required this.rideCount,
    required this.totalDistance,
    required this.totalDuration,
    required this.totalClimb,
    required this.calories,
    required this.avgSpeed,
  });

  final String rideCount;
  final String totalDistance;
  final String totalDuration;
  final String totalClimb;
  final String calories;
  final String avgSpeed;

  factory _RideStats.fromRides(List<RideSession> rides) {
    final totalDistance =
        rides.fold<double>(0, (sum, ride) => sum + ride.distanceKm);
    final totalSeconds =
        rides.fold<int>(0, (sum, ride) => sum + ride.durationSeconds);
    final totalClimb =
        rides.fold<double>(0, (sum, ride) => sum + ride.totalClimbM);
    final avgSpeed = totalSeconds > 0 ? totalDistance / totalSeconds * 3600 : 0;

    return _RideStats(
      rideCount: rides.length.toString(),
      totalDistance: totalDistance.toStringAsFixed(1),
      totalDuration: _formatSeconds(totalSeconds),
      totalClimb: totalClimb.toStringAsFixed(0),
      calories: (totalDistance * 31.73).round().toString(),
      avgSpeed: avgSpeed.toStringAsFixed(1),
    );
  }
}

String _formatDuration(Duration duration) {
  return _formatSeconds(duration.inSeconds);
}

String _formatSeconds(int seconds) {
  final hours = seconds ~/ 3600;
  final minutes = (seconds % 3600) ~/ 60;
  final secs = seconds % 60;
  return [
    hours.toString().padLeft(2, '0'),
    minutes.toString().padLeft(2, '0'),
    secs.toString().padLeft(2, '0'),
  ].join(':');
}

class _RouteMapPainter extends CustomPainter {
  const _RouteMapPainter({
    this.variant = 0,
    this.track = const [],
    this.gpxTrack = const <_GpxPoint>[],
  });

  final int variant;
  final List<RidePoint> track;
  final List<_GpxPoint> gpxTrack;

  @override
  void paint(Canvas canvas, Size size) {
    final bgPaint = Paint()
      ..shader = LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [
          const Color(0xFF1F2833).withOpacity(0.92),
          const Color(0xFF10161F).withOpacity(0.98),
        ],
      ).createShader(Offset.zero & size);
    canvas.drawRect(Offset.zero & size, bgPaint);

    _drawMapLines(canvas, size);
    // 有有效真实轨迹则画真实轨迹，否则兜底示例环线
    final projected = _projectGpxTrack(size) ?? _projectTrack(size);
    if (projected != null) {
      _drawPolyline(canvas, projected);
    } else {
      _drawRoute(canvas, size);
    }
  }

  // 将真实 GPS 轨迹等比投影到画布；点不足/坐标非法/跨度过小时返回 null（兜底）
  List<Offset>? _projectGpxTrack(Size size) {
    if (gpxTrack.length < 2) return null;
    return _projectCoordinates(
      size,
      gpxTrack.map((point) => _TrackCoordinate(point.lat, point.lon)),
    );
  }

  List<Offset>? _projectTrack(Size size) {
    if (track.length < 2) return null;
    return _projectCoordinates(
      size,
      track.map((point) => _TrackCoordinate(point.latitude, point.longitude)),
    );
  }

  List<Offset>? _projectCoordinates(
    Size size,
    Iterable<_TrackCoordinate> coordinates,
  ) {
    var minLat = double.infinity;
    var maxLat = -double.infinity;
    var minLon = double.infinity;
    var maxLon = -double.infinity;
    final validCoordinates = <_TrackCoordinate>[];
    for (final p in coordinates) {
      final lat = p.lat;
      final lon = p.lon;
      if (!lat.isFinite || !lon.isFinite) continue;
      if (lat == 0 && lon == 0) continue;
      validCoordinates.add(p);
      minLat = math.min(minLat, lat);
      maxLat = math.max(maxLat, lat);
      minLon = math.min(minLon, lon);
      maxLon = math.max(maxLon, lon);
    }
    if (validCoordinates.length < 2) return null;
    final latSpan = maxLat - minLat;
    final lonSpan = maxLon - minLon;
    if (latSpan <= 1e-7 && lonSpan <= 1e-7) return null;
    const pad = 16.0;
    final w = size.width - pad * 2;
    final h = size.height - pad * 2;
    if (w <= 0 || h <= 0) return null;
    final span = math.max(latSpan, lonSpan);
    final scale = math.min(w, h) / span;
    final offsetX = pad + (w - lonSpan * scale) / 2;
    final offsetY = pad + (h - latSpan * scale) / 2;
    final pts = <Offset>[];
    for (final p in validCoordinates) {
      final x = offsetX + (p.lon - minLon) * scale;
      final y = offsetY + (maxLat - p.lat) * scale;
      pts.add(Offset(x, y));
    }
    return pts.length >= 2 ? pts : null;
  }

  void _drawPolyline(Canvas canvas, List<Offset> pts) {
    final shadow = Paint()
      ..color = Colors.black.withOpacity(0.34)
      ..strokeWidth = 11
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round;
    final path = Path()..moveTo(pts.first.dx, pts.first.dy);
    for (final p in pts.skip(1)) {
      path.lineTo(p.dx, p.dy);
    }
    canvas.drawPath(path, shadow);
    for (var i = 0; i < pts.length - 1; i++) {
      final t = pts.length <= 2 ? 0.0 : i / (pts.length - 2);
      final color =
          Color.lerp(const Color(0xFF57DF43), const Color(0xFFFF4B24), t)!;
      canvas.drawPath(
        Path()
          ..moveTo(pts[i].dx, pts[i].dy)
          ..lineTo(pts[i + 1].dx, pts[i + 1].dy),
        Paint()
          ..color = color
          ..strokeWidth = 5.8
          ..style = PaintingStyle.stroke
          ..strokeCap = StrokeCap.round
          ..strokeJoin = StrokeJoin.round,
      );
    }
    canvas.drawCircle(pts.first, 9, Paint()..color = const Color(0xFF5FE052));
    canvas.drawCircle(pts.first, 4, Paint()..color = Colors.white);
    canvas.drawCircle(pts.last, 8, Paint()..color = Colors.white);
    canvas.drawCircle(
        pts.last, 4, Paint()..color = Colors.black.withOpacity(0.78));
  }

  void _drawMapLines(Canvas canvas, Size size) {
    final roadPaint = Paint()
      ..color = Colors.white.withOpacity(0.045)
      ..strokeWidth = 2
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;
    final thinRoadPaint = Paint()
      ..color = Colors.white.withOpacity(0.028)
      ..strokeWidth = 1.2
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;

    for (var i = 0; i < 6; i++) {
      final y = size.height * (0.12 + i * 0.17);
      final path = Path()
        ..moveTo(-20, y + variant * 4)
        ..cubicTo(
          size.width * 0.26,
          y - 24,
          size.width * 0.58,
          y + 30,
          size.width + 20,
          y - 8,
        );
      canvas.drawPath(path, i.isEven ? roadPaint : thinRoadPaint);
    }

    for (var i = 0; i < 4; i++) {
      final x = size.width * (0.18 + i * 0.24);
      final path = Path()
        ..moveTo(x, -16)
        ..cubicTo(
          x + 30,
          size.height * 0.26,
          x - 30,
          size.height * 0.60,
          x + 14,
          size.height + 16,
        );
      canvas.drawPath(path, thinRoadPaint);
    }
  }

  void _drawRoute(Canvas canvas, Size size) {
    final route = _routePoints(size);
    final shadow = Paint()
      ..color = Colors.black.withOpacity(0.34)
      ..strokeWidth = 11
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round;
    final path = Path()..moveTo(route.first.dx, route.first.dy);
    for (final point in route.skip(1)) {
      path.lineTo(point.dx, point.dy);
    }
    canvas.drawPath(path, shadow);

    for (var i = 0; i < route.length - 1; i++) {
      final segmentPath = Path()
        ..moveTo(route[i].dx, route[i].dy)
        ..lineTo(route[i + 1].dx, route[i + 1].dy);
      final t = i / (route.length - 2);
      final color = Color.lerp(
        const Color(0xFF57DF43),
        const Color(0xFFFF4B24),
        t,
      )!;
      canvas.drawPath(
        segmentPath,
        Paint()
          ..color = color
          ..strokeWidth = 5.8
          ..style = PaintingStyle.stroke
          ..strokeCap = StrokeCap.round
          ..strokeJoin = StrokeJoin.round,
      );
    }

    canvas.drawCircle(route.first, 9, Paint()..color = const Color(0xFF5FE052));
    canvas.drawCircle(route.first, 4, Paint()..color = Colors.white);
    final finish = route[math.max(0, route.length - 3)];
    canvas.drawCircle(finish, 8, Paint()..color = Colors.white);
    canvas.drawCircle(finish, 4, Paint()..color = Colors.black.withOpacity(0.78));
  }

  List<Offset> _routePoints(Size size) {
    final dx = (variant % 2) * size.width * 0.04;
    final dy = (variant % 3) * size.height * 0.025;
    return [
      Offset(size.width * 0.62 - dx, size.height * 0.10 + dy),
      Offset(size.width * 0.50 - dx, size.height * 0.20 + dy),
      Offset(size.width * 0.42 - dx, size.height * 0.34 + dy),
      Offset(size.width * 0.31 - dx, size.height * 0.41 + dy),
      Offset(size.width * 0.42 + dx, size.height * 0.56),
      Offset(size.width * 0.56 + dx, size.height * 0.52),
      Offset(size.width * 0.72 + dx, size.height * 0.63),
      Offset(size.width * 0.64 + dx, size.height * 0.79),
      Offset(size.width * 0.48, size.height * 0.88 - dy),
      Offset(size.width * 0.39 - dx, size.height * 0.70 - dy),
      Offset(size.width * 0.24 - dx, size.height * 0.58 - dy),
      Offset(size.width * 0.28 - dx, size.height * 0.38),
      Offset(size.width * 0.46, size.height * 0.28),
      Offset(size.width * 0.62 - dx, size.height * 0.10 + dy),
    ];
  }

  @override
  bool shouldRepaint(covariant _RouteMapPainter oldDelegate) {
    return oldDelegate.variant != variant ||
        oldDelegate.track != track ||
        oldDelegate.gpxTrack != gpxTrack;
  }
}

class _TrackCoordinate {
  const _TrackCoordinate(this.lat, this.lon);

  final double lat;
  final double lon;
}

class _SparklinePainter extends CustomPainter {
  const _SparklinePainter({
    required this.values,
    required this.color,
  });

  final List<double> values;
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    if (values.length < 2) return;
    final minValue = values.reduce(math.min);
    final maxValue = values.reduce(math.max);
    final range = math.max(1, maxValue - minValue);
    final path = Path();
    for (var i = 0; i < values.length; i++) {
      final x = size.width * i / (values.length - 1);
      final normalized = (values[i] - minValue) / range;
      final y = size.height - normalized * size.height * 0.82 - 3;
      if (i == 0) {
        path.moveTo(x, y);
      } else {
        path.lineTo(x, y);
      }
    }
    final fill = Path.from(path)
      ..lineTo(size.width, size.height)
      ..lineTo(0, size.height)
      ..close();
    canvas.drawPath(
      fill,
      Paint()
        ..shader = LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [color.withOpacity(0.42), color.withOpacity(0.0)],
        ).createShader(Offset.zero & size),
    );
    canvas.drawPath(
      path,
      Paint()
        ..color = color
        ..strokeWidth = 1.6
        ..style = PaintingStyle.stroke
        ..strokeCap = StrokeCap.round
        ..strokeJoin = StrokeJoin.round,
    );
  }

  @override
  bool shouldRepaint(covariant _SparklinePainter oldDelegate) {
    return oldDelegate.values != values || oldDelegate.color != color;
  }
}

class _InteractiveElevationChart extends StatefulWidget {
  const _InteractiveElevationChart({
    required this.values,
    required this.color,
  });

  final List<double> values;
  final Color color;

  @override
  State<_InteractiveElevationChart> createState() =>
      _InteractiveElevationChartState();
}

class _InteractiveElevationChartState
    extends State<_InteractiveElevationChart> {
  Timer? _hideTimer;
  double? _selectedT;

  @override
  void dispose() {
    _hideTimer?.cancel();
    super.dispose();
  }

  void _hideSelection() {
    if (_selectedT == null) return;
    _hideTimer?.cancel();
    setState(() => _selectedT = null);
  }

  void _selectAt(Offset localPosition, Size size) {
    final t = _tForPosition(localPosition, size);
    if (t == null) {
      _hideSelection();
      return;
    }
    _hideTimer?.cancel();
    setState(() => _selectedT = t);
    _hideTimer = Timer(const Duration(seconds: 3), () {
      if (mounted) setState(() => _selectedT = null);
    });
  }

  double? _tForPosition(Offset localPosition, Size size) {
    if (widget.values.length < 2) return null;
    final rect = _elevationChartRect(size);
    if (rect.width <= 0) return null;
    return ((localPosition.dx - rect.left) / rect.width)
        .clamp(0.0, 1.0)
        .toDouble();
  }

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final size = Size(constraints.maxWidth, constraints.maxHeight);
        return TapRegion(
          onTapOutside: (_) => _hideSelection(),
          child: Listener(
            behavior: HitTestBehavior.opaque,
            onPointerDown: (event) => _selectAt(event.localPosition, size),
            onPointerMove: (event) => _selectAt(event.localPosition, size),
            onPointerCancel: (_) => _hideSelection(),
            child: CustomPaint(
              painter: _ElevationLineChartPainter(
                values: widget.values,
                color: widget.color,
                selectedT: _selectedT,
              ),
              child: const SizedBox.expand(),
            ),
          ),
        );
      },
    );
  }
}

Rect _elevationChartRect(Size size) =>
    Rect.fromLTRB(28, 10, size.width - 14, size.height - 20);

class _ElevationLineChartPainter extends CustomPainter {
  const _ElevationLineChartPainter({
    required this.values,
    required this.color,
    this.selectedT,
  });

  final List<double> values;
  final Color color;
  final double? selectedT;

  @override
  void paint(Canvas canvas, Size size) {
    if (values.length < 2) return;
    final rect = _elevationChartRect(size);
    if (rect.width <= 0 || rect.height <= 0) return;

    final minValue = values.reduce(math.min);
    final maxValue = values.reduce(math.max);
    final range = math.max(1.0, maxValue - minValue);

    _drawGrid(canvas, rect);
    _drawAxisLabels(canvas, size, rect, minValue, maxValue);

    final path = Path();
    for (var i = 0; i < values.length; i++) {
      final point = _pointForIndex(i, rect, minValue, range);
      if (i == 0) {
        path.moveTo(point.dx, point.dy);
      } else {
        path.lineTo(point.dx, point.dy);
      }
    }

    final fill = Path.from(path)
      ..lineTo(rect.right, rect.bottom)
      ..lineTo(rect.left, rect.bottom)
      ..close();
    canvas.drawPath(
      fill,
      Paint()
        ..shader = LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [color.withOpacity(0.34), color.withOpacity(0.02)],
        ).createShader(rect),
    );
    canvas.drawPath(
      path,
      Paint()
        ..color = color
        ..strokeWidth = 2.2
        ..style = PaintingStyle.stroke
        ..strokeCap = StrokeCap.round
        ..strokeJoin = StrokeJoin.round,
    );

    _drawSelection(canvas, size, rect, minValue, range);
  }

  Offset _pointForIndex(
    int index,
    Rect rect,
    double minValue,
    double range,
  ) {
    final x = rect.left + rect.width * index / (values.length - 1);
    final normalized = (values[index] - minValue) / range;
    final y = rect.bottom - rect.height * normalized.clamp(0.0, 1.0);
    return Offset(x, y);
  }

  void _drawGrid(Canvas canvas, Rect rect) {
    final grid = Paint()
      ..color = Colors.white.withOpacity(0.08)
      ..strokeWidth = 1;
    for (var i = 0; i <= 2; i++) {
      final y = rect.bottom - rect.height * i / 2;
      canvas.drawLine(Offset(rect.left, y), Offset(rect.right, y), grid);
    }
  }

  void _drawAxisLabels(
    Canvas canvas,
    Size size,
    Rect rect,
    double minValue,
    double maxValue,
  ) {
    _drawLabel(
      canvas,
      '${_formatChartValue(maxValue, 'm')}m',
      Offset(0, rect.top - 2),
      color: Colors.white.withOpacity(0.44),
      size: 10,
    );
    _drawLabel(
      canvas,
      '${_formatChartValue(minValue, 'm')}m',
      Offset(0, rect.bottom - 10),
      color: Colors.white.withOpacity(0.44),
      size: 10,
    );

    const progressLabels = ['0%', '50%', '100%'];
    for (var i = 0; i < progressLabels.length; i++) {
      final x = rect.left + rect.width * i / (progressLabels.length - 1);
      _drawLabel(
        canvas,
        progressLabels[i],
        Offset(x, size.height - 13),
        color: Colors.white.withOpacity(0.42),
        size: 10,
        center: true,
      );
    }
  }

  void _drawSelection(
    Canvas canvas,
    Size size,
    Rect rect,
    double minValue,
    double range,
  ) {
    final t = selectedT;
    if (t == null) return;
    final index = (t.clamp(0.0, 1.0) * (values.length - 1))
        .round()
        .clamp(0, values.length - 1)
        .toInt();
    final point = _pointForIndex(index, rect, minValue, range);

    canvas.drawLine(
      Offset(point.dx, rect.top),
      Offset(point.dx, rect.bottom),
      Paint()
        ..color = Colors.white.withOpacity(0.16)
        ..strokeWidth = 1,
    );
    canvas.drawCircle(point, 5.5, Paint()..color = color);
    canvas.drawCircle(
      point,
      2.6,
      Paint()..color = Colors.white.withOpacity(0.92),
    );

    _drawTooltip(
      canvas,
      size: size,
      anchor: point,
      title: '路线点 ${index + 1}/${values.length}',
      value: '${_formatChartValue(values[index], 'm')} m',
    );
  }

  void _drawTooltip(
    Canvas canvas, {
    required Size size,
    required Offset anchor,
    required String title,
    required String value,
  }) {
    final titlePainter = _textPainter(
      title,
      color: Colors.white.withOpacity(0.66),
      size: 10,
      weight: FontWeight.w700,
    );
    final valuePainter = _textPainter(
      value,
      color: Colors.white,
      size: 13,
      weight: FontWeight.w900,
    );
    final width = math.max(titlePainter.width, valuePainter.width) + 24;
    const height = 48.0;
    final centerX = _clampDouble(anchor.dx, width / 2, size.width - width / 2);
    final top = _clampDouble(anchor.dy - height - 14, 4, size.height - height - 4);
    final rect = RRect.fromRectAndRadius(
      Rect.fromLTWH(centerX - width / 2, top, width, height),
      const Radius.circular(9),
    );
    canvas.drawRRect(
      rect,
      Paint()..color = const Color(0xFF303744).withOpacity(0.96),
    );
    canvas.drawRRect(
      rect,
      Paint()
        ..color = color.withOpacity(0.32)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1,
    );
    titlePainter.paint(
      canvas,
      Offset(centerX - titlePainter.width / 2, top + 7),
    );
    valuePainter.paint(
      canvas,
      Offset(centerX - valuePainter.width / 2, top + 25),
    );
  }

  void _drawLabel(
    Canvas canvas,
    String text,
    Offset offset, {
    required Color color,
    required double size,
    bool center = false,
  }) {
    final painter = _textPainter(
      text,
      color: color,
      size: size,
      weight: FontWeight.w700,
    );
    painter.paint(
      canvas,
      Offset(offset.dx - (center ? painter.width / 2 : 0), offset.dy),
    );
  }

  @override
  bool shouldRepaint(covariant _ElevationLineChartPainter oldDelegate) {
    return oldDelegate.values != values ||
        oldDelegate.color != color ||
        oldDelegate.selectedT != selectedT;
  }
}

class _InteractiveDualLineChart extends StatefulWidget {
  const _InteractiveDualLineChart({
    required this.speed,
    required this.altitude,
    required this.duration,
  });

  final List<double> speed;
  final List<double> altitude;
  final Duration duration;

  @override
  State<_InteractiveDualLineChart> createState() =>
      _InteractiveDualLineChartState();
}

class _InteractiveDualLineChartState extends State<_InteractiveDualLineChart> {
  Timer? _hideTimer;
  double? _selectedT;

  @override
  void dispose() {
    _hideTimer?.cancel();
    super.dispose();
  }

  void _hideSelection() {
    if (_selectedT == null) return;
    _hideTimer?.cancel();
    setState(() => _selectedT = null);
  }

  void _selectAt(Offset localPosition, Size size) {
    final t = _tForPosition(localPosition, size);
    if (t == null) {
      _hideSelection();
      return;
    }
    _hideTimer?.cancel();
    setState(() => _selectedT = t);
    _hideTimer = Timer(const Duration(seconds: 3), () {
      if (mounted) setState(() => _selectedT = null);
    });
  }

  double? _tForPosition(Offset localPosition, Size size) {
    if (widget.speed.length < 2 && widget.altitude.length < 2) return null;
    final rect = _dualLineChartRect(size);
    return ((localPosition.dx - rect.left) / rect.width)
        .clamp(0.0, 1.0)
        .toDouble();
  }

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final size = Size(constraints.maxWidth, constraints.maxHeight);
        return TapRegion(
          onTapOutside: (_) => _hideSelection(),
          child: Listener(
            behavior: HitTestBehavior.opaque,
            onPointerDown: (event) => _selectAt(event.localPosition, size),
            onPointerMove: (event) => _selectAt(event.localPosition, size),
            child: CustomPaint(
              painter: _DualLineChartPainter(
                speed: widget.speed,
                altitude: widget.altitude,
                duration: widget.duration,
                selectedT: _selectedT,
              ),
              child: const SizedBox.expand(),
            ),
          ),
        );
      },
    );
  }
}

Rect _dualLineChartRect(Size size) =>
    Rect.fromLTRB(21, 24, size.width - 25, size.height - 15);

class _DualLineChartPainter extends CustomPainter {
  const _DualLineChartPainter({
    required this.speed,
    required this.altitude,
    required this.duration,
    this.selectedT,
  });

  final List<double> speed;
  final List<double> altitude;
  final Duration duration;
  final double? selectedT;

  static const _speedMax = 60.0;
  static const _altMax = 1500.0;

  // 两侧各仅留一列刻度的窄边距，曲线区尽量拉宽（贴近设计图近满屏宽）。
  Rect _chartRect(Size size) => _dualLineChartRect(size);

  @override
  void paint(Canvas canvas, Size size) {
    final rect = _chartRect(size);
    final grid = Paint()
      ..color = Colors.white.withOpacity(0.08)
      ..strokeWidth = 1;
    // 单位与刻度成列：左列(km/h + 60/40/20)统一左对齐，右列(m + 1500/1000/500)统一右对齐。
    const levels = 4;
    _drawAxisText(canvas, 'km/h', const Offset(1, 3));
    _drawAxisText(canvas, 'm', Offset(size.width - 1, 3), alignRight: true);
    for (var i = 0; i < levels; i++) {
      final t = i / (levels - 1);
      final y = rect.bottom - rect.height * t;
      canvas.drawLine(Offset(rect.left, y), Offset(rect.right, y), grid);
      if (i == 0) continue; // 跳过 0 刻度：仅显示 20/40/60 与 500/1000/1500
      _drawTick(canvas, (_speedMax * t).round().toString(),
          Offset(1, y - 5), alignRight: false);
      _drawTick(canvas, (_altMax * t).round().toString(),
          Offset(size.width - 1, y - 5), alignRight: true);
    }

    _drawSeries(canvas, rect, altitude, const Color(0xFFA533FF), _altMax);
    _drawSeries(canvas, rect, speed, const Color(0xFF2B9DFF), _speedMax);

    final labels = _timeAxisLabels(duration, count: 6);
    for (var i = 0; i < labels.length; i++) {
      final x = rect.left + rect.width * i / (labels.length - 1);
      _drawChartLabel(canvas, labels[i], Offset(x, size.height - 12), center: true);
    }

    _drawSelection(canvas, size, rect);
  }

  void _drawTick(
    Canvas canvas,
    String text,
    Offset anchor, {
    required bool alignRight,
  }) {
    final painter = TextPainter(
      text: TextSpan(
        text: text,
        style: TextStyle(
          color: Colors.white.withOpacity(0.40),
          fontSize: 9,
          fontWeight: FontWeight.w700,
        ),
      ),
      textDirection: TextDirection.ltr,
    )..layout();
    final dx = alignRight ? anchor.dx - painter.width : anchor.dx;
    painter.paint(canvas, Offset(dx, anchor.dy));
  }

  void _drawSeries(
    Canvas canvas,
    Rect chartRect,
    List<double> data,
    Color color,
    double maxValue,
  ) {
    if (data.length < 2 || maxValue <= 0) return;
    final path = Path();
    for (var i = 0; i < data.length; i++) {
      final x = chartRect.left + chartRect.width * i / (data.length - 1);
      final value = data[i].clamp(0, maxValue);
      final y = chartRect.bottom - chartRect.height * (value / maxValue);
      if (i == 0) {
        path.moveTo(x, y);
      } else {
        path.lineTo(x, y);
      }
    }
    final fill = Path.from(path)
      ..lineTo(chartRect.right, chartRect.bottom)
      ..lineTo(chartRect.left, chartRect.bottom)
      ..close();
    canvas.drawPath(
      fill,
      Paint()
        ..shader = LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [color.withOpacity(0.34), color.withOpacity(0.02)],
        ).createShader(chartRect),
    );
    canvas.drawPath(
      path,
      Paint()
        ..color = color
        ..strokeWidth = 2.2
        ..style = PaintingStyle.stroke
        ..strokeCap = StrokeCap.round
        ..strokeJoin = StrokeJoin.round,
    );
  }

  void _drawAxisText(Canvas canvas, String text, Offset offset,
      {bool alignRight = false}) {
    final painter = TextPainter(
      text: TextSpan(
        text: text,
        style: TextStyle(
          color: Colors.white.withOpacity(0.62),
          fontSize: 11,
          fontWeight: FontWeight.w800,
        ),
      ),
      textDirection: TextDirection.ltr,
    )..layout();
    final dx = alignRight ? offset.dx - painter.width : offset.dx;
    painter.paint(canvas, Offset(dx, offset.dy));
  }

  void _drawChartLabel(
    Canvas canvas,
    String text,
    Offset offset, {
    bool center = false,
  }) {
    final painter = TextPainter(
      text: TextSpan(
        text: text,
        style: TextStyle(
          color: Colors.white.withOpacity(0.46),
          fontSize: 10,
          fontWeight: FontWeight.w700,
        ),
      ),
      textDirection: TextDirection.ltr,
    )..layout();
    painter.paint(canvas, Offset(offset.dx - (center ? painter.width / 2 : 0), offset.dy));
  }

  void _drawSelection(Canvas canvas, Size size, Rect rect) {
    final t = selectedT;
    if (t == null) return;
    final clampedT = t.clamp(0.0, 1.0).toDouble();
    final x = rect.left + rect.width * clampedT;
    canvas.drawLine(
      Offset(x, rect.top),
      Offset(x, rect.bottom),
      Paint()
        ..color = Colors.white.withOpacity(0.16)
        ..strokeWidth = 1,
    );

    final speedSelection = _seriesSelection(
      data: speed,
      chartRect: rect,
      color: const Color(0xFF2B9DFF),
      maxValue: _speedMax,
      t: clampedT,
    );
    final altitudeSelection = _seriesSelection(
      data: altitude,
      chartRect: rect,
      color: const Color(0xFFA533FF),
      maxValue: _altMax,
      t: clampedT,
    );

    if (speedSelection != null) _drawSelectionPoint(canvas, speedSelection);
    if (altitudeSelection != null) {
      _drawSelectionPoint(canvas, altitudeSelection);
    }

    final title = _timeLabelForT(clampedT, duration);
    final rows = <_ChartTooltipRow>[
      if (speedSelection != null)
        _ChartTooltipRow(
          label: '速度',
          value: '${_formatChartValue(speedSelection.value, 'km/h')} km/h',
          color: speedSelection.color,
        ),
      if (altitudeSelection != null)
        _ChartTooltipRow(
          label: '海拔',
          value: '${_formatChartValue(altitudeSelection.value, 'm')} m',
          color: altitudeSelection.color,
        ),
    ];
    if (rows.isEmpty) return;

    final anchor = speedSelection?.point ??
        altitudeSelection?.point ??
        Offset(x, rect.center.dy);
    _drawMultiRowTooltip(canvas, size, anchor, title, rows);
  }

  _SeriesSelection? _seriesSelection({
    required List<double> data,
    required Rect chartRect,
    required Color color,
    required double maxValue,
    required double t,
  }) {
    if (data.length < 2 || maxValue <= 0) return null;
    final index = (t * (data.length - 1))
        .round()
        .clamp(0, data.length - 1)
        .toInt();
    final value = data[index].clamp(0.0, maxValue).toDouble();
    final x = chartRect.left + chartRect.width * index / (data.length - 1);
    final y = chartRect.bottom - chartRect.height * value / maxValue;
    return _SeriesSelection(
      point: Offset(x, y),
      value: value,
      color: color,
    );
  }

  void _drawSelectionPoint(Canvas canvas, _SeriesSelection selection) {
    canvas.drawCircle(
      selection.point,
      5,
      Paint()..color = selection.color,
    );
    canvas.drawCircle(
      selection.point,
      2.4,
      Paint()..color = Colors.white.withOpacity(0.92),
    );
  }

  void _drawMultiRowTooltip(
    Canvas canvas,
    Size size,
    Offset anchor,
    String title,
    List<_ChartTooltipRow> rows,
  ) {
    final titlePainter = _textPainter(
      title,
      color: Colors.white.withOpacity(0.66),
      size: 10,
      weight: FontWeight.w700,
    );
    final labelPainters = [
      for (final row in rows)
        _textPainter(
          row.label,
          color: row.color,
          size: 11,
          weight: FontWeight.w900,
        ),
    ];
    final valuePainters = [
      for (final row in rows)
        _textPainter(
          row.value,
          color: Colors.white,
          size: 12,
          weight: FontWeight.w900,
        ),
    ];
    var width = titlePainter.width + 24;
    for (var i = 0; i < rows.length; i++) {
      width =
          math.max(width, labelPainters[i].width + valuePainters[i].width + 32);
    }
    final height = 28.0 + rows.length * 18.0;
    final centerX = _clampDouble(anchor.dx, width / 2, size.width - width / 2);
    final top = _clampDouble(anchor.dy - height - 14, 4, size.height - height - 4);
    final rect = RRect.fromRectAndRadius(
      Rect.fromLTWH(centerX - width / 2, top, width, height),
      const Radius.circular(9),
    );
    canvas.drawRRect(
      rect,
      Paint()..color = const Color(0xFF303744).withOpacity(0.96),
    );
    titlePainter.paint(canvas, Offset(centerX - titlePainter.width / 2, top + 7));
    for (var i = 0; i < rows.length; i++) {
      final y = top + 24 + i * 18;
      labelPainters[i].paint(canvas, Offset(rect.left + 11, y));
      valuePainters[i].paint(
        canvas,
        Offset(rect.right - valuePainters[i].width - 11, y),
      );
    }
  }

  @override
  bool shouldRepaint(covariant _DualLineChartPainter oldDelegate) {
    return oldDelegate.speed != speed ||
        oldDelegate.altitude != altitude ||
        oldDelegate.duration != duration ||
        oldDelegate.selectedT != selectedT;
  }
}

class _BarChartPainter extends CustomPainter {
  const _BarChartPainter({
    required this.values,
    required this.labels,
    required this.color,
    required this.maxValue,
    required this.tooltipIndex,
    required this.tooltipTitle,
    required this.tooltipValue,
    this.labelIndices,
  });

  final List<double> values;
  final List<String> labels;
  final List<int>? labelIndices;
  final Color color;
  final double maxValue;
  final int? tooltipIndex;
  final String tooltipTitle;
  final String tooltipValue;

  @override
  void paint(Canvas canvas, Size size) {
    if (values.isEmpty || maxValue <= 0) return;
    final chartRect = Rect.fromLTWH(34, 26, size.width - 54, size.height - 52);
    final grid = Paint()
      ..color = Colors.white.withOpacity(0.07)
      ..strokeWidth = 1;
    for (var i = 0; i <= 4; i++) {
      final y = chartRect.bottom - chartRect.height * i / 4;
      canvas.drawLine(Offset(chartRect.left, y), Offset(chartRect.right, y), grid);
      _drawText(
        canvas,
        (maxValue * i / 4).round().toString(),
        Offset(0, y - 7),
        color: Colors.white.withOpacity(0.46),
        size: 11,
      );
    }

    final barWidth = math.max(4.0, chartRect.width / values.length * 0.34);
    for (var i = 0; i < values.length; i++) {
      final value = values[i].clamp(0, maxValue);
      final x = chartRect.left + chartRect.width * (i + 0.5) / values.length;
      final height = chartRect.height * value / maxValue;
      final rect = RRect.fromRectAndRadius(
        Rect.fromLTWH(x - barWidth / 2, chartRect.bottom - height, barWidth, height),
        const Radius.circular(3),
      );
      canvas.drawRRect(
        rect,
        Paint()
          ..shader = LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [color, color.withOpacity(0.70)],
          ).createShader(rect.outerRect),
      );
    }

    final labelPositions = labelIndices;
    for (var i = 0; i < labels.length; i++) {
      int? valueIndex;
      if (labelPositions != null && i < labelPositions.length) {
        valueIndex = labelPositions[i].clamp(0, values.length - 1).toInt();
      }
      final x = valueIndex == null
          ? labels.length == 1
              ? chartRect.center.dx
              : chartRect.left + chartRect.width * i / (labels.length - 1)
          : chartRect.left + chartRect.width * (valueIndex + 0.5) / values.length;
      _drawText(
        canvas,
        labels[i],
        Offset(x, size.height - 20),
        color: Colors.white.withOpacity(0.48),
        size: 12,
        center: true,
      );
    }

    final selectedIndex = tooltipIndex;
    if (selectedIndex == null || selectedIndex >= values.length) return;
    final markerX =
        chartRect.left + chartRect.width * (selectedIndex + 0.5) / values.length;
    final markerY = chartRect.bottom -
        chartRect.height * values[selectedIndex].clamp(0, maxValue) / maxValue;
    _drawTooltip(canvas, Offset(markerX, markerY - 10), size);
  }

  void _drawTooltip(Canvas canvas, Offset anchor, Size size) {
    final centerX = math.min(
      math.max(anchor.dx, 43.0),
      math.max(43.0, size.width - 43.0),
    );
    final centerY = math.max(anchor.dy, 70.0);
    final adjustedAnchor = Offset(centerX, centerY);
    final rect = RRect.fromRectAndRadius(
      Rect.fromCenter(
        center: adjustedAnchor.translate(0, -36),
        width: 86,
        height: 58,
      ),
      const Radius.circular(10),
    );
    canvas.drawRRect(
      rect,
      Paint()..color = const Color(0xFF303744).withOpacity(0.96),
    );
    final pointer = Path()
      ..moveTo(adjustedAnchor.dx - 8, adjustedAnchor.dy - 8)
      ..lineTo(adjustedAnchor.dx + 8, adjustedAnchor.dy - 8)
      ..lineTo(adjustedAnchor.dx, adjustedAnchor.dy + 1)
      ..close();
    canvas.drawPath(
      pointer,
      Paint()..color = const Color(0xFF303744).withOpacity(0.96),
    );
    _drawText(canvas, tooltipTitle, Offset(adjustedAnchor.dx, adjustedAnchor.dy - 61),
        color: Colors.white.withOpacity(0.82), size: 12, center: true);
    _drawText(canvas, tooltipValue, Offset(adjustedAnchor.dx, adjustedAnchor.dy - 40),
        color: Colors.white, size: 14, center: true, bold: true);
  }

  void _drawText(
    Canvas canvas,
    String text,
    Offset offset, {
    required Color color,
    required double size,
    bool center = false,
    bool bold = false,
  }) {
    final painter = TextPainter(
      text: TextSpan(
        text: text,
        style: TextStyle(
          color: color,
          fontSize: size,
          fontWeight: bold ? FontWeight.w900 : FontWeight.w700,
        ),
      ),
      textDirection: TextDirection.ltr,
    )..layout();
    painter.paint(
      canvas,
      Offset(offset.dx - (center ? painter.width / 2 : 0), offset.dy),
    );
  }

  @override
  bool shouldRepaint(covariant _BarChartPainter oldDelegate) {
    return oldDelegate.values != values ||
        oldDelegate.labels != labels ||
        oldDelegate.labelIndices != labelIndices ||
        oldDelegate.color != color ||
        oldDelegate.maxValue != maxValue ||
        oldDelegate.tooltipIndex != tooltipIndex ||
        oldDelegate.tooltipTitle != tooltipTitle ||
        oldDelegate.tooltipValue != tooltipValue;
  }
}
class _DonutPainter extends CustomPainter {
  const _DonutPainter({
    required this.colors,
    required this.values,
    required this.backgroundColor,
    this.strokeWidth = 16,
    this.selectedIndex,
  });

  final List<Color> colors;
  final List<double> values;
  final Color backgroundColor;
  final double strokeWidth;
  final int? selectedIndex;

  @override
  void paint(Canvas canvas, Size size) {
    if (values.isEmpty) return;
    final center = Offset(size.width / 2, size.height / 2);
    final radius = math.min(size.width, size.height) * 0.38;
    var start = -math.pi / 2;
    final hasSelection = selectedIndex != null;
    for (var i = 0; i < values.length; i++) {
      final sweep = values[i] * math.pi * 2;
      final isSelected = selectedIndex == i;
      canvas.drawArc(
        Rect.fromCircle(center: center, radius: radius),
        start,
        math.max(0.0, sweep - 0.035),
        false,
        Paint()
          ..color = hasSelection && !isSelected
              ? colors[i].withOpacity(0.42)
              : colors[i]
          ..style = PaintingStyle.stroke
          ..strokeWidth = isSelected ? strokeWidth + 3 : strokeWidth
          ..strokeCap = StrokeCap.butt,
      );
      start += sweep;
    }
    canvas.drawCircle(center, radius - strokeWidth / 1.9, Paint()..color = backgroundColor);
  }

  @override
  bool shouldRepaint(covariant _DonutPainter oldDelegate) {
    return oldDelegate.colors != colors ||
        oldDelegate.values != values ||
        oldDelegate.strokeWidth != strokeWidth ||
        oldDelegate.selectedIndex != selectedIndex;
  }
}

class _RadarPainter extends CustomPainter {
  const _RadarPainter({this.sweepStart = 0, this.active = true});

  // 扫描扇形的起始角（弧度）；由 AnimationController 循环驱动旋转。
  final double sweepStart;
  // 是否扫描中：停止时只保留静态雷达网格、不画旋转扇形。
  final bool active;

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = math.min(size.width, size.height) * 0.46;
    if (radius <= 0) return;
    final ring = Paint()
      ..color = Colors.white.withOpacity(0.10)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1;
    for (var i = 1; i <= 4; i++) {
      canvas.drawCircle(center, radius * i / 4, ring);
    }
    canvas.drawLine(
      Offset(center.dx - radius, center.dy),
      Offset(center.dx + radius, center.dy),
      ring,
    );
    canvas.drawLine(
      Offset(center.dx, center.dy - radius),
      Offset(center.dx, center.dy + radius),
      ring,
    );

    if (!active) return;
    canvas.drawArc(
      Rect.fromCircle(center: center, radius: radius),
      sweepStart,
      math.pi / 2,
      true,
      Paint()
        ..shader = RadialGradient(
          colors: [
            const Color(0xFF42E343).withOpacity(0.08),
            const Color(0xFF42E343).withOpacity(0.52),
          ],
        ).createShader(Rect.fromCircle(center: center, radius: radius)),
    );
  }

  @override
  bool shouldRepaint(covariant _RadarPainter oldDelegate) =>
      oldDelegate.sweepStart != sweepStart || oldDelegate.active != active;
}

void _showUiMessage(String title, String message) {
  Get.snackbar(
    title,
    message,
    snackPosition: SnackPosition.BOTTOM,
    duration: const Duration(seconds: 2),
  );
}

Future<void> _shareText(
  BuildContext context, {
  required String title,
  required String text,
}) async {
  try {
    final result = await SharePlus.instance.share(
      ShareParams(
        title: title,
        subject: title,
        text: text,
        sharePositionOrigin: _sharePositionOrigin(context),
      ),
    );
    if (result.status == ShareResultStatus.unavailable) {
      await _copyShareText(text);
    }
  } catch (_) {
    await _copyShareText(text);
  }
}

Future<void> _copyShareText(String text) async {
  await Clipboard.setData(ClipboardData(text: text));
  _showUiMessage('分享不可用', '内容已复制到剪贴板');
}

Rect? _sharePositionOrigin(BuildContext context) {
  final renderObject = context.findRenderObject();
  if (renderObject is! RenderBox || !renderObject.hasSize) return null;
  return renderObject.localToGlobal(Offset.zero) & renderObject.size;
}

Future<void> _shareCurrentRide(
  BuildContext context,
) {
  return _shareRouteSummary(
    context,
    title: '户外骑行',
  );
}

Future<void> _shareRouteSummary(
  BuildContext context, {
  required String title,
}) async {
  final shareTitle = '分享路线 - $title';
  final shareUri = _routeShareUri();

  try {
    final result = await SharePlus.instance.share(
      ShareParams(
        title: shareTitle,
        uri: shareUri,
        sharePositionOrigin: _sharePositionOrigin(context),
      ),
    );
    if (result.status == ShareResultStatus.unavailable) {
      await _copyShareText(shareUri.toString());
    }
  } catch (_) {
    await _copyShareText(shareUri.toString());
  }
}

Uri _routeShareUri() {
  return ShareLinks.landingPageUri;
}

String _routeSummaryText({
  required String title,
  required String date,
  required String distance,
  required String climb,
  required String duration,
  required String difficulty,
}) {
  return '''
Trace 路线分享
$title
日期: $date
距离: $distance km
爬升: $climb m
用时: $duration
难度: $difficulty
''';
}

void _openConnectedDeviceDetail() {
  _openRidePage(
    () => const _RideDeviceDetailPage(
      name: 'iGPSPORT BSC300_1234',
      type: '码表',
    ),
  );
}

Future<void> _showDeviceSyncActions(BuildContext context) {
  return _showDeviceActionSheet(
    context,
    actionsBuilder: (sheetContext) => [
      _RouteMoreAction(
        icon: Icons.sync,
        label: '同步骑行记录',
        onTap: () {
          Navigator.of(sheetContext).pop();
          _showUiMessage('同步骑行记录', '正在同步码表中的骑行记录');
        },
      ),
      _RouteMoreAction(
        icon: Icons.settings_backup_restore,
        label: '同步设备配置',
        onTap: () {
          Navigator.of(sheetContext).pop();
          _showUiMessage('同步设备配置', '正在同步页面、传感器与骑行设置');
        },
      ),
      _RouteMoreAction(
        icon: Icons.system_update_alt,
        label: '检查固件更新',
        onTap: () {
          Navigator.of(sheetContext).pop();
          Get.to(() => const OtaUpgradePage());
        },
      ),
    ],
  );
}

Future<void> _showDeviceMoreActions(BuildContext context) {
  return _showDeviceActionSheet(
    context,
    actionsBuilder: (sheetContext) => [
      _RouteMoreAction(
        icon: Icons.info_outline,
        label: '设备详情',
        onTap: () {
          Navigator.of(sheetContext).pop();
          _openConnectedDeviceDetail();
        },
      ),
      _RouteMoreAction(
        icon: Icons.grid_view,
        label: '页面配置',
        onTap: () {
          Navigator.of(sheetContext).pop();
          _showUiMessage('页面配置', '已打开码表页面配置');
        },
      ),
      _RouteMoreAction(
        icon: Icons.sensors,
        label: '传感器管理',
        onTap: () {
          Navigator.of(sheetContext).pop();
          _showUiMessage('传感器管理', '已打开已配对传感器列表');
        },
      ),
      Divider(color: Colors.white.withOpacity(0.08), height: 8),
      _RouteMoreAction(
        icon: Icons.link_off,
        label: '解除绑定',
        color: const Color(0xFFFF3B5F),
        onTap: () {
          Navigator.of(sheetContext).pop();
          _showUiMessage('解除绑定', '已打开设备解绑确认');
        },
      ),
    ],
  );
}

Future<void> _showRouteFilterActions(
  BuildContext context, {
  required int selectedIndex,
  required ValueChanged<int> onSelect,
}) {
  return _showDeviceActionSheet(
    context,
    actionsBuilder: (sheetContext) => [
      for (var i = 0; i < _routeFilterLabels.length; i++)
        _RouteMoreAction(
          icon: i == selectedIndex
              ? Icons.check_circle
              : Icons.radio_button_unchecked,
          label: _routeFilterLabels[i],
          onTap: () {
            Navigator.of(sheetContext).pop();
            onSelect(i);
          },
        ),
    ],
  );
}

Future<void> _showMissingDeviceActions(
  BuildContext context, {
  required VoidCallback onRefresh,
}) {
  return _showDeviceActionSheet(
    context,
    actionsBuilder: (sheetContext) => [
      _RouteMoreAction(
        icon: Icons.refresh,
        label: '重新扫描',
        onTap: () {
          Navigator.of(sheetContext).pop();
          onRefresh();
        },
      ),
      _RouteMoreAction(
        icon: Icons.add_link,
        label: '手动添加设备',
        onTap: () {
          Navigator.of(sheetContext).pop();
          _showUiMessage('手动添加设备', '已打开设备名称或序列号添加入口');
        },
      ),
      _RouteMoreAction(
        icon: Icons.help_outline,
        label: '连接帮助',
        onTap: () {
          Navigator.of(sheetContext).pop();
          _showUiMessage('连接帮助', '请确认设备已开机、蓝牙已开启并靠近手机');
        },
      ),
    ],
  );
}

Future<void> _showDeviceActionSheet(
  BuildContext context, {
  required List<Widget> Function(BuildContext sheetContext) actionsBuilder,
}) {
  return showModalBottomSheet<void>(
    context: context,
    backgroundColor: Colors.transparent,
    builder: (sheetContext) {
      return SafeArea(
        child: Container(
          margin: const EdgeInsets.fromLTRB(14, 0, 14, 14),
          padding: const EdgeInsets.fromLTRB(12, 10, 12, 12),
          decoration: BoxDecoration(
            color: const Color(0xFF171D27),
            borderRadius: BorderRadius.circular(18),
            border: Border.all(color: Colors.white.withOpacity(0.08)),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withOpacity(0.42),
                blurRadius: 28,
                offset: const Offset(0, 12),
              ),
            ],
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: actionsBuilder(sheetContext),
          ),
        ),
      );
    },
  );
}

Future<void> _showRouteMoreActions(
  BuildContext context, {
  required String title,
  required String date,
  required String distance,
  required String climb,
  required String duration,
  required String difficulty,
  VoidCallback? onDelete,
}) {
  final summary = _routeSummaryText(
    title: title,
    date: date,
    distance: distance,
    climb: climb,
    duration: duration,
    difficulty: difficulty,
  );

  return showModalBottomSheet<void>(
    context: context,
    backgroundColor: Colors.transparent,
    builder: (sheetContext) {
      return SafeArea(
        child: Container(
          margin: const EdgeInsets.fromLTRB(14, 0, 14, 14),
          padding: const EdgeInsets.fromLTRB(12, 10, 12, 12),
          decoration: BoxDecoration(
            color: const Color(0xFF171D27),
            borderRadius: BorderRadius.circular(18),
            border: Border.all(color: Colors.white.withOpacity(0.08)),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withOpacity(0.42),
                blurRadius: 28,
                offset: const Offset(0, 12),
              ),
            ],
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              _RouteMoreAction(
                icon: Icons.send_to_mobile,
                label: '发送到设备',
                onTap: () {
                  Navigator.of(sheetContext).pop();
                  _showUiMessage('发送到设备', '$title 已加入发送队列');
                },
              ),
              _RouteMoreAction(
                icon: Icons.copy,
                label: '复制路线信息',
                onTap: () async {
                  Navigator.of(sheetContext).pop();
                  await Clipboard.setData(ClipboardData(text: summary));
                  _showUiMessage('复制成功', '路线信息已复制到剪贴板');
                },
              ),
              _RouteMoreAction(
                icon: Icons.share_outlined,
                label: '分享路线',
                onTap: () {
                  Navigator.of(sheetContext).pop();
                  _shareRouteSummary(
                    context,
                    title: title,
                  );
                },
              ),
              if (onDelete != null) ...[
                Divider(color: Colors.white.withOpacity(0.08), height: 8),
                _RouteMoreAction(
                  icon: Icons.delete_outline,
                  label: '删除路线',
                  color: const Color(0xFFFF3B5F),
                  onTap: () {
                    Navigator.of(sheetContext).pop();
                    onDelete();
                  },
                ),
              ],
            ],
          ),
        ),
      );
    },
  );
}

Future<bool> _showRouteDeleteConfirmDialog(
  BuildContext context,
  String title,
) async {
  final result = await showDialog<bool>(
    context: context,
    barrierDismissible: true,
    builder: (dialogContext) {
      return AlertDialog(
        backgroundColor: const Color(0xFF171D27),
        surfaceTintColor: Colors.transparent,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(18),
          side: BorderSide(color: Colors.white.withOpacity(0.08)),
        ),
        title: const Text(
          '删除路线？',
          style: TextStyle(
            color: Colors.white,
            fontWeight: FontWeight.w900,
          ),
        ),
        content: Text(
          '确认删除「$title」？删除后无法恢复。',
          style: TextStyle(
            color: Colors.white.withOpacity(0.72),
            height: 1.4,
            fontWeight: FontWeight.w700,
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: Text(
              '取消',
              style: TextStyle(color: Colors.white.withOpacity(0.72)),
            ),
          ),
          FilledButton(
            style: FilledButton.styleFrom(
              backgroundColor: const Color(0xFFFF3B5F),
              foregroundColor: Colors.white,
            ),
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: const Text(
              '确认删除',
              style: TextStyle(fontWeight: FontWeight.w900),
            ),
          ),
        ],
      );
    },
  );
  return result ?? false;
}

class _RouteMoreAction extends StatelessWidget {
  const _RouteMoreAction({
    required this.icon,
    required this.label,
    required this.onTap,
    this.color,
  });

  final IconData icon;
  final String label;
  final VoidCallback onTap;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    final actionColor = color ?? _RideColors.orange;
    return InkWell(
      borderRadius: BorderRadius.circular(12),
      onTap: onTap,
      child: SizedBox(
        height: 50,
        child: Row(
          children: [
            const SizedBox(width: 8),
            Icon(icon, color: actionColor, size: 22),
            const SizedBox(width: 14),
            Text(
              label,
              style: TextStyle(
                color: color ?? Colors.white,
                fontSize: 16,
                fontWeight: FontWeight.w800,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// 码表模块统一页面跳转：强制使用 Cupertino 横向滑动转场。
// 主题为浅色（Brightness.light）而码表全部页面为深色背景，若使用 Material3 默认的
// Zoom 转场，动画期间会绘制一层主题 surface（浅色）填充背景，与深色页面反差即表现为
// 进入/返回时的屏幕闪烁。横向滑动转场不绘制该浅色层，可彻底消除闪烁。
void _openRidePage(Widget Function() page) {
  Get.to<void>(
    page,
    transition: Transition.cupertino,
    duration: const Duration(milliseconds: 300),
  );
}

class _RideColors {
  static const background = Color(0xFF070D14);
  static const panel = Color(0xFF171D27);
  static const orange = Color(0xFFFF4B1F);
}
