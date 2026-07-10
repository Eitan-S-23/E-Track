import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:fl_chart/fl_chart.dart';
import 'package:get/get.dart';
import 'package:file_picker/file_picker.dart';
import '../controllers/monitor_controller.dart';
import '../models/device_data.dart';
import '../models/device_settings.dart';
import '../services/alert_service.dart';
import 'power_stats_page.dart';

class DeviceChartPage extends StatefulWidget {
  final String deviceId;

  const DeviceChartPage({Key? key, required this.deviceId}) : super(key: key);

  @override
  State<DeviceChartPage> createState() => _DeviceChartPageState();
}

class _DeviceChartPageState extends State<DeviceChartPage>
    with TickerProviderStateMixin {
  late TabController _tabController;
  MonitorController get monitorController => Get.find<MonitorController>();

  // 日期筛选相关
  DateTime? _startDate;
  DateTime? _endDate;
  List<DeviceData> _filteredData = [];

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    _initializeFilteredData();
  }

  /// 初始化筛选数据
  void _initializeFilteredData() {
    final device = monitorController.selectedDevices
            .firstWhereOrNull((d) => d.deviceId == widget.deviceId) ??
        monitorController.savedDevices
            .firstWhereOrNull((d) => d.deviceId == widget.deviceId);

    if (device != null) {
      _filteredData = List.from(device.dataHistory);
    }
  }

  /// 获取当前设备
  SelectedDevice? _getDevice() {
    return monitorController.selectedDevices
            .firstWhereOrNull((d) => d.deviceId == widget.deviceId) ??
        monitorController.savedDevices
            .firstWhereOrNull((d) => d.deviceId == widget.deviceId);
  }

  /// 获取当前显示的数据（筛选后或全部）
  List<DeviceData> _getCurrentDisplayData(SelectedDevice device) {
    if (_startDate != null || _endDate != null) {
      return _filteredData;
    }
    return device.dataHistory;
  }

  /// 应用日期筛选
  void _applyDateFilter(SelectedDevice device) {
    List<DeviceData> data = List.from(device.dataHistory);

    if (_startDate != null) {
      data = data
          .where((d) =>
              d.timestamp.isAfter(_startDate!) ||
              d.timestamp.isAtSameMomentAs(_startDate!))
          .toList();
    }

    if (_endDate != null) {
      final endOfDay =
          DateTime(_endDate!.year, _endDate!.month, _endDate!.day, 23, 59, 59);
      data = data
          .where((d) =>
              d.timestamp.isBefore(endOfDay) ||
              d.timestamp.isAtSameMomentAs(endOfDay))
          .toList();
    }

    setState(() {
      _filteredData = data;
    });
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final device = monitorController.selectedDevices
            .firstWhereOrNull((d) => d.deviceId == widget.deviceId) ??
        monitorController.savedDevices
            .firstWhereOrNull((d) => d.deviceId == widget.deviceId);

    if (device == null) {
      return Scaffold(
        appBar: AppBar(title: const Text('设备未找到')),
        body: const Center(child: Text('设备数据不存在')),
      );
    }

    return Scaffold(
      backgroundColor: const Color(0xFFF5F7FA),
      appBar: AppBar(
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              device.deviceName,
              style: const TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.w600,
              ),
            ),
            Text(
              '设备监控图表',
              style: TextStyle(
                fontSize: 12,
                color: Colors.grey.shade600,
                fontWeight: FontWeight.normal,
              ),
            ),
          ],
        ),
        backgroundColor: Colors.white,
        foregroundColor: const Color(0xFF2E3A59),
        elevation: 0,
        actions: [
          IconButton(
            icon: const Icon(Icons.analytics),
            onPressed: () {
              Get.to(() => PowerStatsPage(
                    deviceId: device.deviceId,
                    deviceName: device.deviceName,
                  ));
            },
          ),
          IconButton(
            icon: const Icon(Icons.date_range),
            onPressed: () => _showDateFilter(context, device),
          ),
          IconButton(
            icon: const Icon(Icons.settings),
            onPressed: () => _showDeviceSettings(context, device),
          ),
        ],
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(49),
          child: Container(
            color: Colors.white,
            child: TabBar(
              controller: _tabController,
              labelColor: const Color(0xFF4A90E2),
              unselectedLabelColor: Colors.grey.shade600,
              indicatorColor: const Color(0xFF4A90E2),
              indicatorWeight: 3,
              tabs: const [
                Tab(text: '电流'),
                Tab(text: '电压'),
                Tab(text: '功率'),
              ],
            ),
          ),
        ),
      ),
      body: Column(
        children: [
          // 设备状态卡片
          _buildDeviceStatusCard(device),

          // 图表内容
          Expanded(
            child: Obx(() {
              // 监听设备数据变化
              final updatedDevice = monitorController.selectedDevices
                      .firstWhereOrNull((d) => d.deviceId == widget.deviceId) ??
                  monitorController.savedDevices
                      .firstWhereOrNull((d) => d.deviceId == widget.deviceId);

              if (updatedDevice == null) {
                return const Center(child: Text('设备未找到'));
              }

              return TabBarView(
                controller: _tabController,
                children: [
                  _buildCurrentChart(updatedDevice),
                  _buildVoltageChart(updatedDevice),
                  _buildPowerChart(updatedDevice),
                ],
              );
            }),
          ),
        ],
      ),
    );
  }

  Widget _buildDeviceStatusCard(SelectedDevice device) {
    return Obx(() {
      // 直接访问响应式数据
      final latestData = monitorController.realtimeData[device.deviceId];
      final selectedDevice = monitorController.selectedDevices
              .firstWhereOrNull((d) => d.deviceId == device.deviceId) ??
          monitorController.savedDevices
              .firstWhereOrNull((d) => d.deviceId == device.deviceId);
      final powerConsumption = selectedDevice?.powerConsumption ?? 0.0;

      return Container(
        margin: const EdgeInsets.all(16),
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          gradient: const LinearGradient(
            colors: [Color(0xFF4A90E2), Color(0xFF357ABD)],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          borderRadius: BorderRadius.circular(16),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withOpacity(0.1),
              blurRadius: 10,
              offset: const Offset(0, 4),
            ),
          ],
        ),
        child: Column(
          children: [
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: 0.2),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Icon(
                    Icons.electrical_services,
                    color: Colors.white,
                    size: 24,
                  ),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        '实时监控',
                        style: TextStyle(
                          color: Colors.white.withValues(alpha: 0.9),
                          fontSize: 14,
                        ),
                      ),
                      Text(
                        '数据点: ${device.dataHistory.length}',
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 16,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            if (latestData != null) ...[
              const SizedBox(height: 16),
              Row(
                children: [
                  Expanded(
                    child: _buildStatusItem(
                      '电流',
                      '${latestData.current.toStringAsFixed(1)}${latestData.currentUnit}',
                      Icons.flash_on,
                    ),
                  ),
                  Container(
                    width: 1,
                    height: 40,
                    color: Colors.white.withValues(alpha: 0.3),
                  ),
                  Expanded(
                    child: _buildStatusItem(
                      '电压',
                      '${latestData.voltage.toStringAsFixed(1)}mV',
                      Icons.battery_charging_full,
                    ),
                  ),
                  Container(
                    width: 1,
                    height: 40,
                    color: Colors.white.withValues(alpha: 0.3),
                  ),
                  Expanded(
                    child: _buildStatusItem(
                      '功率',
                      '${latestData.power.toStringAsFixed(2)}mW',
                      Icons.power,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Column(
                children: [
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: Colors.white.withValues(alpha: 0.2),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Row(
                      children: [
                        const Icon(
                          Icons.battery_std,
                          color: Colors.white,
                          size: 16,
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Text(
                                '本次记录耗电量: ${_getDevice()?.sessionConsumption.toStringAsFixed(3) ?? '0.000'} mAh',
                                style: const TextStyle(
                                  color: Colors.white,
                                  fontSize: 12,
                                  fontWeight: FontWeight.w500,
                                ),
                                overflow: TextOverflow.ellipsis,
                              ),
                              const SizedBox(height: 2),
                              Text(
                                '累计耗电量: ${powerConsumption.toStringAsFixed(3)} mAh',
                                style: const TextStyle(
                                  color: Colors.white,
                                  fontSize: 14,
                                  fontWeight: FontWeight.w600,
                                ),
                                overflow: TextOverflow.ellipsis,
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 8),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                    children: [
                      Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Container(
                            width: 8,
                            height: 8,
                            decoration: const BoxDecoration(
                              color: Colors.blue,
                              shape: BoxShape.circle,
                            ),
                          ),
                          const SizedBox(width: 4),
                          Text(
                            '广播包',
                            style: TextStyle(
                              color: Colors.white.withValues(alpha: 0.9),
                              fontSize: 10,
                            ),
                          ),
                        ],
                      ),
                      Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Container(
                            width: 8,
                            height: 8,
                            decoration: const BoxDecoration(
                              color: Colors.green,
                              shape: BoxShape.circle,
                            ),
                          ),
                          const SizedBox(width: 4),
                          Text(
                            '扫描响应',
                            style: TextStyle(
                              color: Colors.white.withValues(alpha: 0.9),
                              fontSize: 10,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ],
              ),
            ],
          ],
        ),
      ).animate().fadeIn(duration: 600.ms).slideY(begin: -0.3, end: 0);
    });
  }

  Widget _buildStatusItem(String label, String value, IconData icon) {
    return Column(
      children: [
        Icon(icon, color: Colors.white.withValues(alpha: 0.8), size: 16),
        const SizedBox(height: 4),
        Text(
          label,
          style: TextStyle(
            color: Colors.white.withValues(alpha: 0.8),
            fontSize: 12,
          ),
        ),
        const SizedBox(height: 2),
        Text(
          value,
          style: const TextStyle(
            color: Colors.white,
            fontSize: 14,
            fontWeight: FontWeight.bold,
          ),
        ),
      ],
    );
  }

  Widget _buildCurrentChart(SelectedDevice device) {
    final historyData = _getCurrentDisplayData(device);
    final currentData = _convertCurrentToBestUnit(historyData);

    String title = '电流趋势';
    if (_startDate != null || _endDate != null) {
      title += ' (已筛选)';
    }

    return _buildChartContainer(
      title,
      _createDynamicLineChart(
        historyData,
        currentData['values'],
        currentData['unit'],
        const Color(0xFFFF9800),
      ),
      Icons.flash_on,
      const Color(0xFFFF9800),
    );
  }

  Widget _buildVoltageChart(SelectedDevice device) {
    final historyData = _getCurrentDisplayData(device);
    final voltageData = _convertVoltageToBestUnit(historyData);

    String title = '电压趋势';
    if (_startDate != null || _endDate != null) {
      title += ' (已筛选)';
    }

    return _buildChartContainer(
      title,
      _createDynamicLineChart(
        historyData,
        voltageData['values'],
        voltageData['unit'],
        const Color(0xFF4CAF50),
      ),
      Icons.battery_charging_full,
      const Color(0xFF4CAF50),
    );
  }

  Widget _buildPowerChart(SelectedDevice device) {
    final historyData = _getCurrentDisplayData(device);
    final powerData = _convertPowerToBestUnit(historyData);

    String title = '功率趋势';
    if (_startDate != null || _endDate != null) {
      title += ' (已筛选)';
    }

    return _buildChartContainer(
      title,
      _createDynamicLineChart(
        historyData,
        powerData['values'],
        powerData['unit'],
        const Color(0xFF9C27B0),
      ),
      Icons.power,
      const Color(0xFF9C27B0),
    );
  }

  Widget _buildChartContainer(
      String title, Widget chart, IconData icon, Color color) {
    return Container(
      margin: const EdgeInsets.all(16),
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.05),
            blurRadius: 10,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: color.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Icon(
                  icon,
                  color: color,
                  size: 20,
                ),
              ),
              const SizedBox(width: 12),
              Text(
                title,
                style: const TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w600,
                  color: Color(0xFF2E3A59),
                ),
              ),
            ],
          ),
          const SizedBox(height: 20),
          Expanded(child: chart),
        ],
      ),
    ).animate().fadeIn(duration: 800.ms).slideY(begin: 0.3, end: 0);
  }

  Widget _createDynamicLineChart(
    List<DeviceData> data,
    List<double> values,
    String unit,
    Color lineColor,
  ) {
    if (data.isEmpty || values.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.timeline,
              size: 48,
              color: Colors.grey.shade400,
            ),
            const SizedBox(height: 16),
            Text(
              '暂无数据',
              style: TextStyle(
                fontSize: 16,
                color: Colors.grey.shade600,
              ),
            ),
          ],
        ),
      );
    }

    // Filter data to last 24 hours and optimize points
    final now = DateTime.now();
    final oneDayAgo = now.subtract(const Duration(days: 1));

    final recentData = <DeviceData>[];
    final recentValues = <double>[];

    for (int i = 0; i < data.length; i++) {
      if (data[i].timestamp.isAfter(oneDayAgo)) {
        recentData.add(data[i]);
        recentValues.add(values[i]);
      }
    }

    if (recentData.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.timeline,
              size: 48,
              color: Colors.grey.shade400,
            ),
            const SizedBox(height: 16),
            Text(
              '过去24小时无数据',
              style: TextStyle(
                fontSize: 16,
                color: Colors.grey.shade600,
              ),
            ),
          ],
        ),
      );
    }

    // Optimize data points to reduce crowding (max 200 points)
    final optimizedData = <DeviceData>[];
    final optimizedValues = <double>[];

    if (recentData.length <= 200) {
      optimizedData.addAll(recentData);
      optimizedValues.addAll(recentValues);
    } else {
      final step = recentData.length / 200;
      for (int i = 0; i < 200; i++) {
        final index = (i * step).floor();
        if (index < recentData.length) {
          optimizedData.add(recentData[index]);
          optimizedValues.add(recentValues[index]);
        }
      }
    }

    final spots = <FlSpot>[];
    final startTime =
        optimizedData.first.timestamp.millisecondsSinceEpoch.toDouble();

    for (int i = 0; i < optimizedData.length; i++) {
      final timeOffset =
          optimizedData[i].timestamp.millisecondsSinceEpoch.toDouble() -
              startTime;
      spots.add(FlSpot(timeOffset, optimizedValues[i]));
    }

    final minY = optimizedValues.reduce((a, b) => a < b ? a : b);
    final maxY = optimizedValues.reduce((a, b) => a > b ? a : b);
    final range = maxY - minY;
    final padding = range > 0 ? range * 0.1 : 1.0;

    return LineChart(
      LineChartData(
        minY: minY - padding,
        maxY: maxY + padding,
        lineBarsData: [
          LineChartBarData(
            spots: spots,
            isCurved: true,
            color: lineColor,
            barWidth: 2,
            isStrokeCapRound: true,
            dotData: FlDotData(
              show: optimizedData.length <=
                  50, // Only show dots for small datasets
              getDotPainter: (spot, percent, barData, index) {
                return FlDotCirclePainter(
                  radius: 3,
                  color: lineColor,
                  strokeWidth: 1,
                  strokeColor: Colors.white,
                );
              },
            ),
            belowBarData: BarAreaData(
              show: true,
              color: lineColor.withValues(alpha: 0.1),
            ),
          ),
        ],
        titlesData: FlTitlesData(
          leftTitles: AxisTitles(
            sideTitles: SideTitles(
              showTitles: true,
              reservedSize: 60,
              getTitlesWidget: (value, meta) {
                return Text(
                  '${value.toStringAsFixed(range > 100 ? 0 : 1)}$unit',
                  style: TextStyle(
                    fontSize: 10,
                    color: Colors.grey.shade600,
                  ),
                );
              },
            ),
          ),
          bottomTitles: AxisTitles(
            sideTitles: SideTitles(
              showTitles: true,
              reservedSize: 30,
              interval: (spots.last.x - spots.first.x) / 4,
              getTitlesWidget: (value, meta) {
                final timestamp = DateTime.fromMillisecondsSinceEpoch(
                    (startTime + value).toInt());
                return Text(
                  '${timestamp.hour.toString().padLeft(2, '0')}:${timestamp.minute.toString().padLeft(2, '0')}',
                  style: TextStyle(
                    fontSize: 10,
                    color: Colors.grey.shade600,
                  ),
                );
              },
            ),
          ),
          topTitles:
              const AxisTitles(sideTitles: SideTitles(showTitles: false)),
          rightTitles:
              const AxisTitles(sideTitles: SideTitles(showTitles: false)),
        ),
        gridData: FlGridData(
          show: true,
          drawVerticalLine: true,
          horizontalInterval: range > 0 ? range / 4 : 1,
          verticalInterval: (spots.last.x - spots.first.x) / 4,
          getDrawingHorizontalLine: (value) {
            return FlLine(
              color: Colors.grey.shade200,
              strokeWidth: 1,
            );
          },
          getDrawingVerticalLine: (value) {
            return FlLine(
              color: Colors.grey.shade200,
              strokeWidth: 1,
            );
          },
        ),
        borderData: FlBorderData(
          show: true,
          border: Border.all(
            color: Colors.grey.shade300,
            width: 1,
          ),
        ),
        lineTouchData: LineTouchData(
          enabled: true,
          touchTooltipData: LineTouchTooltipData(
            getTooltipItems: (List<LineBarSpot> touchedBarSpots) {
              return touchedBarSpots.map((barSpot) {
                final timestamp = DateTime.fromMillisecondsSinceEpoch(
                    (startTime + barSpot.x).toInt());
                return LineTooltipItem(
                  '${timestamp.month}/${timestamp.day} ${timestamp.hour.toString().padLeft(2, '0')}:${timestamp.minute.toString().padLeft(2, '0')}\n${barSpot.y.toStringAsFixed(2)}$unit',
                  TextStyle(
                    color: lineColor,
                    fontWeight: FontWeight.bold,
                  ),
                );
              }).toList();
            },
          ),
        ),
      ),
    );
  }

  // Dynamic unit conversion for current
  Map<String, dynamic> _convertCurrentToBestUnit(List<DeviceData> data) {
    if (data.isEmpty)
      return {'values': <double>[], 'unit': 'nA', 'multiplier': 1.0};

    // Convert all values to nA first
    final valuesInNA =
        data.map((d) => _convertCurrentToNA(d.current, d.currentUnit)).toList();
    final maxValue = valuesInNA.reduce((a, b) => a > b ? a : b);

    // Choose best unit based on max value
    if (maxValue >= 1e9) {
      return {
        'values': valuesInNA.map((v) => v / 1e9).toList(),
        'unit': 'A',
        'multiplier': 1e9
      };
    } else if (maxValue >= 1e6) {
      return {
        'values': valuesInNA.map((v) => v / 1e6).toList(),
        'unit': 'mA',
        'multiplier': 1e6
      };
    } else if (maxValue >= 1e3) {
      return {
        'values': valuesInNA.map((v) => v / 1e3).toList(),
        'unit': 'µA',
        'multiplier': 1e3
      };
    } else {
      return {'values': valuesInNA, 'unit': 'nA', 'multiplier': 1.0};
    }
  }

  double _convertCurrentToNA(double current, String unit) {
    switch (unit) {
      case 'nA':
        return current;
      case 'uA':
        return current * 1000.0;
      case 'mA':
        return current * 1000000.0;
      case 'A':
        return current * 1000000000.0;
      default:
        return 0.0;
    }
  }

  // Dynamic unit conversion for voltage
  Map<String, dynamic> _convertVoltageToBestUnit(List<DeviceData> data) {
    if (data.isEmpty)
      return {'values': <double>[], 'unit': 'mV', 'multiplier': 1.0};

    final voltages = data.map((d) => d.voltage).toList();
    final maxVoltage = voltages.reduce((a, b) => a > b ? a : b);

    if (maxVoltage >= 1000.0) {
      return {
        'values': voltages.map((v) => v / 1000.0).toList(),
        'unit': 'V',
        'multiplier': 1000.0
      };
    } else {
      return {'values': voltages, 'unit': 'mV', 'multiplier': 1.0};
    }
  }

  // Dynamic unit conversion for power
  Map<String, dynamic> _convertPowerToBestUnit(List<DeviceData> data) {
    if (data.isEmpty)
      return {'values': <double>[], 'unit': 'mW', 'multiplier': 1.0};

    final powers = data.map((d) => d.power).toList();
    final maxPower = powers.reduce((a, b) => a > b ? a : b);

    if (maxPower >= 1000.0) {
      return {
        'values': powers.map((p) => p / 1000.0).toList(),
        'unit': 'W',
        'multiplier': 1000.0
      };
    } else {
      return {'values': powers, 'unit': 'mW', 'multiplier': 1.0};
    }
  }

  /// 显示日期筛选对话框
  void _showDateFilter(BuildContext context, SelectedDevice device) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Row(
          children: [
            Icon(Icons.date_range, color: Color(0xFF4A90E2)),
            SizedBox(width: 8),
            Text('筛选日期范围'),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            // 开始日期
            ListTile(
              leading: const Icon(Icons.calendar_today),
              title: Text(_startDate == null
                  ? '选择开始日期'
                  : '开始: ${_formatDate(_startDate!)}'),
              onTap: () async {
                final date = await showDatePicker(
                  context: context,
                  initialDate: _startDate ??
                      DateTime.now().subtract(const Duration(days: 7)),
                  firstDate: DateTime(2020),
                  lastDate: DateTime.now(),
                );
                if (date != null) {
                  setState(() {
                    _startDate = date;
                    _updateFilteredData(); // 立即更新过滤数据
                  });
                }
              },
            ),

            // 结束日期
            ListTile(
              leading: const Icon(Icons.event),
              title: Text(_endDate == null
                  ? '选择结束日期'
                  : '结束: ${_formatDate(_endDate!)}'),
              onTap: () async {
                final date = await showDatePicker(
                  context: context,
                  initialDate: _endDate ?? DateTime.now(),
                  firstDate: _startDate ?? DateTime(2020),
                  lastDate: DateTime.now(),
                );
                if (date != null) {
                  setState(() {
                    _endDate = date;
                    _updateFilteredData(); // 立即更新过滤数据
                  });
                }
              },
            ),

            const SizedBox(height: 16),

            // 快速选择按钮
            Wrap(
              spacing: 8,
              children: [
                _buildQuickDateButton('今天', () {
                  final today = DateTime.now();
                  setState(() {
                    _startDate = DateTime(today.year, today.month, today.day);
                    _endDate = today;
                    _updateFilteredData(); // 立即更新过滤数据
                  });
                }),
                _buildQuickDateButton('最近7天', () {
                  final today = DateTime.now();
                  setState(() {
                    _startDate = today.subtract(const Duration(days: 7));
                    _endDate = today;
                    _updateFilteredData(); // 立即更新过滤数据
                  });
                }),
                _buildQuickDateButton('最近30天', () {
                  final today = DateTime.now();
                  setState(() {
                    _startDate = today.subtract(const Duration(days: 30));
                    _endDate = today;
                    _updateFilteredData(); // 立即更新过滤数据
                  });
                }),
              ],
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () {
              setState(() {
                _startDate = null;
                _endDate = null;
                _filteredData = List.from(device.dataHistory);
              });
              Navigator.pop(context);
            },
            child: const Text('清除筛选'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('取消'),
          ),
          ElevatedButton(
            onPressed: () {
              _applyDateFilter(device);
              Navigator.pop(context);
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF4A90E2),
              foregroundColor: Colors.white,
            ),
            child: const Text('应用'),
          ),
        ],
      ),
    );
  }

  Widget _buildQuickDateButton(String label, VoidCallback onPressed) {
    return OutlinedButton(
      onPressed: onPressed,
      style: OutlinedButton.styleFrom(
        foregroundColor: const Color(0xFF4A90E2),
        side: const BorderSide(color: Color(0xFF4A90E2)),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(8),
        ),
      ),
      child: Text(label, style: const TextStyle(fontSize: 12)),
    );
  }

  String _formatDate(DateTime date) {
    return '${date.year}-${date.month.toString().padLeft(2, '0')}-${date.day.toString().padLeft(2, '0')}';
  }

  /// 显示设备设置对话框
  void _showDeviceSettings(BuildContext context, SelectedDevice device) async {
    final alertService = Get.find<AlertService>();
    final settings = await alertService.getDeviceSettings(device.deviceId);

    showDialog(
      context: context,
      builder: (context) => DeviceSettingsDialog(
        device: device,
        settings: settings,
      ),
    );
  }

  /// 更新过滤数据
  void _updateFilteredData() {
    final device = monitorController.selectedDevices
            .firstWhereOrNull((d) => d.deviceId == widget.deviceId) ??
        monitorController.savedDevices
            .firstWhereOrNull((d) => d.deviceId == widget.deviceId);

    if (device != null) {
      List<DeviceData> data = List.from(device.dataHistory);

      if (_startDate != null) {
        data = data
            .where((d) =>
                d.timestamp.isAfter(_startDate!) ||
                d.timestamp.isAtSameMomentAs(_startDate!))
            .toList();
      }

      if (_endDate != null) {
        final endOfDay = DateTime(
            _endDate!.year, _endDate!.month, _endDate!.day, 23, 59, 59);
        data = data
            .where((d) =>
                d.timestamp.isBefore(endOfDay) ||
                d.timestamp.isAtSameMomentAs(endOfDay))
            .toList();
      }

      _filteredData = data;
    }
  }
}

/// 设备设置对话框
class DeviceSettingsDialog extends StatefulWidget {
  final SelectedDevice device;
  final DeviceSettings settings;

  const DeviceSettingsDialog({
    Key? key,
    required this.device,
    required this.settings,
  }) : super(key: key);

  @override
  State<DeviceSettingsDialog> createState() => _DeviceSettingsDialogState();
}

class _DeviceSettingsDialogState extends State<DeviceSettingsDialog> {
  late TextEditingController _currentController;
  late TextEditingController _voltageController;
  late TextEditingController _powerController;
  late TextEditingController _powerConsumptionController;

  late String _currentUnit;
  late String _voltageUnit;
  late String _powerUnit;
  late String _powerConsumptionUnit;
  late bool _alertEnabled;
  late AlertType _alertType;
  String? _customSoundPath;

  @override
  void initState() {
    super.initState();
    _currentController = TextEditingController(
        text: widget.settings.currentThreshold.toString());
    _voltageController = TextEditingController(
        text: widget.settings.voltageThreshold.toString());
    _powerController =
        TextEditingController(text: widget.settings.powerThreshold.toString());
    _powerConsumptionController = TextEditingController(
        text: widget.settings.powerConsumptionThreshold.toString());

    _currentUnit = widget.settings.currentUnit;
    _voltageUnit = widget.settings.voltageUnit;
    _powerUnit = widget.settings.powerUnit;
    _powerConsumptionUnit = widget.settings.powerConsumptionUnit;
    _alertEnabled = widget.settings.alertEnabled;
    _alertType = widget.settings.alertType;
    _customSoundPath = widget.settings.customSoundPath;
  }

  @override
  void dispose() {
    _currentController.dispose();
    _voltageController.dispose();
    _powerController.dispose();
    _powerConsumptionController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Row(
        children: [
          const Icon(Icons.settings, color: Color(0xFF4A90E2)),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('设备设置'),
                Text(
                  widget.device.deviceName,
                  style: TextStyle(
                    fontSize: 12,
                    color: Colors.grey.shade600,
                    fontWeight: FontWeight.normal,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // 报警开关
            SwitchListTile(
              title: const Text('启用异常报警'),
              subtitle: const Text('超出阈值时触发报警'),
              value: _alertEnabled,
              onChanged: (value) {
                setState(() {
                  _alertEnabled = value;
                });
              },
            ),

            if (_alertEnabled) ...[
              const SizedBox(height: 16),

              // 报警类型选择
              const Text(
                '报警方式',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: 8),
              ...AlertType.values
                  .map((type) => RadioListTile<AlertType>(
                        title: Text(_getAlertTypeName(type)),
                        value: type,
                        groupValue: _alertType,
                        onChanged: (value) {
                          setState(() {
                            _alertType = value!;
                          });
                        },
                      ))
                  .toList(),

              // 自定义铃声选择（仅当选择声音或震动+声音时显示）
              if (_alertType == AlertType.sound ||
                  _alertType == AlertType.both) ...[
                const SizedBox(height: 16),
                const Text(
                  '自定义铃声',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 8),
                ListTile(
                  leading: const Icon(Icons.music_note),
                  title: Text(_customSoundPath != null &&
                          _customSoundPath!.isNotEmpty
                      ? '已选择: ${_customSoundPath!.split('/').last.split('\\').last}'
                      : '使用默认铃声'),
                  subtitle:
                      _customSoundPath != null && _customSoundPath!.isNotEmpty
                          ? Text(_customSoundPath!,
                              style: const TextStyle(fontSize: 12),
                              overflow: TextOverflow.ellipsis)
                          : const Text('点击选择自定义铃声文件'),
                  trailing:
                      _customSoundPath != null && _customSoundPath!.isNotEmpty
                          ? IconButton(
                              icon: const Icon(Icons.clear),
                              onPressed: () {
                                setState(() {
                                  _customSoundPath = null;
                                });
                              },
                            )
                          : null,
                  onTap: _selectCustomSound,
                ),
              ],

              const SizedBox(height: 16),

              // 阈值设置
              const Text(
                '阈值设置',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: 16),

              // 电流阈值
              _buildThresholdField(
                '电流阈值',
                _currentController,
                _currentUnit,
                ['nA', 'uA', 'mA', 'A'],
                (unit) => setState(() => _currentUnit = unit),
              ),

              const SizedBox(height: 16),

              // 电压阈值
              _buildThresholdField(
                '电压阈值',
                _voltageController,
                _voltageUnit,
                ['mV', 'V'],
                (unit) => setState(() => _voltageUnit = unit),
              ),

              const SizedBox(height: 16),

              // 功率阈值
              _buildThresholdField(
                '功率阈值',
                _powerController,
                _powerUnit,
                ['mW', 'W'],
                (unit) => setState(() => _powerUnit = unit),
              ),

              const SizedBox(height: 16),

              // 耗电量阈值
              _buildThresholdField(
                '耗电量阈值',
                _powerConsumptionController,
                _powerConsumptionUnit,
                ['mAh', 'Ah'],
                (unit) => setState(() => _powerConsumptionUnit = unit),
              ),
            ],
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('取消'),
        ),
        ElevatedButton(
          onPressed: _saveSettings,
          style: ElevatedButton.styleFrom(
            backgroundColor: const Color(0xFF4A90E2),
            foregroundColor: Colors.white,
          ),
          child: const Text('保存'),
        ),
      ],
    );
  }

  Widget _buildThresholdField(
    String label,
    TextEditingController controller,
    String selectedUnit,
    List<String> units,
    Function(String) onUnitChanged,
  ) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(
          child: TextField(
            controller: controller,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            decoration: InputDecoration(
              labelText: label,
              border: const OutlineInputBorder(),
              contentPadding: const EdgeInsets.symmetric(
                horizontal: 12,
                vertical: 10,
              ),
            ),
          ),
        ),
        const SizedBox(width: 8),
        IntrinsicWidth(
          child: DropdownButtonFormField<String>(
            value: selectedUnit,
            decoration: const InputDecoration(
              border: OutlineInputBorder(),
              contentPadding: EdgeInsets.symmetric(
                horizontal: 8,
                vertical: 10,
              ),
            ),
            items: units
                .map((unit) => DropdownMenuItem(
                      value: unit,
                      child: Text(unit),
                    ))
                .toList(),
            onChanged: (value) {
              if (value != null) {
                onUnitChanged(value);
              }
            },
          ),
        ),
      ],
    );
  }

  String _getAlertTypeName(AlertType type) {
    switch (type) {
      case AlertType.vibration:
        return '震动';
      case AlertType.sound:
        return '铃声';
      case AlertType.both:
        return '震动 + 铃声';
    }
  }

  /// 选择自定义铃声文件
  Future<void> _selectCustomSound() async {
    try {
      FilePickerResult? result = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['mp3', 'wav', 'ogg', 'm4a', 'aac'],
        dialogTitle: '选择报警铃声文件',
      );

      if (result != null && result.files.single.path != null) {
        setState(() {
          _customSoundPath = result.files.single.path;
        });

        Get.snackbar(
          '成功',
          '已选择自定义铃声',
          snackPosition: SnackPosition.BOTTOM,
          backgroundColor: Colors.green,
          colorText: Colors.white,
          duration: const Duration(seconds: 2),
        );
      }
    } catch (e) {
      Get.snackbar(
        '错误',
        '选择文件失败: $e',
        snackPosition: SnackPosition.BOTTOM,
        backgroundColor: Colors.red,
        colorText: Colors.white,
      );
    }
  }

  void _saveSettings() async {
    try {
      final currentThreshold = double.tryParse(_currentController.text);
      final voltageThreshold = double.tryParse(_voltageController.text);
      final powerThreshold = double.tryParse(_powerController.text);
      final powerConsumptionThreshold =
          double.tryParse(_powerConsumptionController.text);

      if (currentThreshold == null || currentThreshold <= 0) {
        Get.snackbar('错误', '请输入有效的电流阈值');
        return;
      }

      if (voltageThreshold == null || voltageThreshold <= 0) {
        Get.snackbar('错误', '请输入有效的电压阈值');
        return;
      }

      if (powerThreshold == null || powerThreshold <= 0) {
        Get.snackbar('错误', '请输入有效的功率阈值');
        return;
      }

      if (powerConsumptionThreshold == null || powerConsumptionThreshold <= 0) {
        Get.snackbar('错误', '请输入有效的耗电量阈值');
        return;
      }

      final newSettings = widget.settings.copyWith(
        currentThreshold: currentThreshold,
        voltageThreshold: voltageThreshold,
        powerThreshold: powerThreshold,
        powerConsumptionThreshold: powerConsumptionThreshold,
        currentUnit: _currentUnit,
        voltageUnit: _voltageUnit,
        powerUnit: _powerUnit,
        powerConsumptionUnit: _powerConsumptionUnit,
        alertEnabled: _alertEnabled,
        alertType: _alertType,
        customSoundPath: _customSoundPath, // 添加自定义铃声路径
      );

      final alertService = Get.find<AlertService>();
      await alertService.saveDeviceSettings(newSettings);

      Navigator.pop(context);

      Get.snackbar(
        '成功',
        '设备设置已保存',
        snackPosition: SnackPosition.BOTTOM,
        backgroundColor: Colors.green,
        colorText: Colors.white,
      );
    } catch (e) {
      Get.snackbar('错误', '保存设置失败: $e');
    }
  }
}
