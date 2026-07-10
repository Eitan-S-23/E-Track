import 'package:flutter/material.dart';
import 'package:fl_chart/fl_chart.dart';
import 'package:get/get.dart';
import '../controllers/monitor_controller.dart';

class PowerStatsPage extends StatefulWidget {
  final String deviceId;
  final String deviceName;

  const PowerStatsPage({
    Key? key,
    required this.deviceId,
    required this.deviceName,
  }) : super(key: key);

  @override
  State<PowerStatsPage> createState() => _PowerStatsPageState();
}

class _PowerStatsPageState extends State<PowerStatsPage>
    with TickerProviderStateMixin {
  late TabController _tabController;
  final monitorController = Get.find<MonitorController>();

  double _totalConsumption = 0.0;
  List<Map<String, dynamic>> _dailyStats = [];
  List<Map<String, dynamic>> _monthlyStats = [];
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    _loadPowerStats();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  void _loadPowerStats() {
    setState(() {
      _isLoading = true;
    });

    try {
      // 使用设备对象中的数组数据来获取统计信息
      final device = monitorController.selectedDevices.firstWhere(
          (d) => d.deviceId == widget.deviceId,
          orElse: () => monitorController.savedDevices
              .firstWhere((d) => d.deviceId == widget.deviceId));

      if (device != null) {
        // 近一年总耗电量直接由月度数组累加得到
        _totalConsumption = device.totalConsumptionOneYear;

        // 获取每日统计（使用数组中的数据）
        _dailyStats = device.getDailyConsumptionStats(days: 30);

        // 获取月度统计（使用数组中的数据）
        _monthlyStats = device.getMonthlyConsumptionStats(months: 12);
      } else {
        // 如果找不到设备，使用传统方法
        _totalConsumption =
            monitorController.getDeviceTotalConsumption(widget.deviceId);
        _dailyStats = monitorController
            .getDeviceDailyConsumptionStats(widget.deviceId, days: 30);
        _monthlyStats = monitorController
            .getDeviceMonthlyConsumptionStats(widget.deviceId, months: 12);
      }

      setState(() {
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _isLoading = false;
      });
      Get.snackbar('错误', '加载耗电量数据失败: $e');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF8F9FA),
      appBar: AppBar(
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              '耗电量统计',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.w600,
              ),
            ),
            Text(
              widget.deviceName,
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
            icon: const Icon(Icons.refresh),
            onPressed: _loadPowerStats,
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
                Tab(text: '总览'),
                Tab(text: '每日'),
                Tab(text: '月度'),
              ],
            ),
          ),
        ),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : TabBarView(
              controller: _tabController,
              children: [
                _buildOverviewTab(),
                _buildDailyTab(),
                _buildMonthlyTab(),
              ],
            ),
    );
  }

  Widget _buildOverviewTab() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 总耗电量卡片
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(24),
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [
                  Color(0xFF4A90E2),
                  Color(0xFF357ABD),
                ],
              ),
              borderRadius: BorderRadius.circular(16),
              boxShadow: [
                BoxShadow(
                  color: const Color(0xFF4A90E2).withOpacity(0.3),
                  blurRadius: 12,
                  offset: const Offset(0, 4),
                ),
              ],
            ),
            child: Column(
              children: [
                const Icon(
                  Icons.battery_std,
                  size: 48,
                  color: Colors.white,
                ),
                const SizedBox(height: 16),
                const Text(
                  '近一年总耗电量',
                  style: TextStyle(
                    fontSize: 16,
                    color: Colors.white70,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  '${_totalConsumption.toStringAsFixed(2)} mAh',
                  style: const TextStyle(
                    fontSize: 32,
                    fontWeight: FontWeight.bold,
                    color: Colors.white,
                  ),
                ),
              ],
            ),
          ),

          const SizedBox(height: 24),

          // 统计信息
          const Text(
            '统计信息',
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w600,
              color: Color(0xFF2E3A59),
            ),
          ),

          const SizedBox(height: 16),

          // 最近7天耗电量
          _buildStatCard(
            '最近7天',
            _calculateRecentConsumption(7),
            Icons.calendar_view_week,
            const Color(0xFF4CAF50),
          ),

          const SizedBox(height: 12),

          // 最近30天耗电量
          _buildStatCard(
            '最近30天',
            _calculateRecentConsumption(30),
            Icons.calendar_view_month,
            const Color(0xFFFF9800),
          ),

          const SizedBox(height: 12),

          // 日均耗电量
          _buildStatCard(
            '日均耗电量',
            _calculateAverageDaily(),
            Icons.trending_up,
            const Color(0xFF9C27B0),
          ),
        ],
      ),
    );
  }

  Widget _buildDailyTab() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 每日图表
          Container(
            height: 300,
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(16),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withOpacity(0.05),
                  blurRadius: 8,
                  offset: const Offset(0, 2),
                ),
              ],
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  '每日耗电量趋势',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w600,
                    color: Color(0xFF2E3A59),
                  ),
                ),
                const SizedBox(height: 16),
                Expanded(
                  child: _buildDailyChart(),
                ),
              ],
            ),
          ),

          const SizedBox(height: 24),

          // 每日排行
          const Text(
            '每日耗电量排行（前10天）',
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w600,
              color: Color(0xFF2E3A59),
            ),
          ),

          const SizedBox(height: 16),

          ..._buildDailyRanking(),
        ],
      ),
    );
  }

  Widget _buildMonthlyTab() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 月度图表
          Container(
            height: 300,
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(16),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withOpacity(0.05),
                  blurRadius: 8,
                  offset: const Offset(0, 2),
                ),
              ],
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  '月度耗电量趋势',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w600,
                    color: Color(0xFF2E3A59),
                  ),
                ),
                const SizedBox(height: 16),
                Expanded(
                  child: _buildMonthlyChart(),
                ),
              ],
            ),
          ),

          const SizedBox(height: 24),

          // 月度排行
          const Text(
            '月度耗电量排行',
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w600,
              color: Color(0xFF2E3A59),
            ),
          ),

          const SizedBox(height: 16),

          ..._buildMonthlyRanking(),
        ],
      ),
    );
  }

  Widget _buildStatCard(
      String title, double value, IconData icon, Color color) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withOpacity(0.2)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.05),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: color.withOpacity(0.1),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Icon(
              icon,
              color: color,
              size: 24,
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: TextStyle(
                    fontSize: 14,
                    color: Colors.grey.shade600,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  '${value.toStringAsFixed(2)} mAh',
                  style: const TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.w600,
                    color: Color(0xFF2E3A59),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildDailyChart() {
    if (_dailyStats.isEmpty) {
      return const Center(child: Text('暂无数据'));
    }

    final spots = _dailyStats.asMap().entries.map((entry) {
      final index = entry.key;
      final data = entry.value;
      return FlSpot(index.toDouble(), (data['consumption'] as num).toDouble());
    }).toList();

    // 计算最大值和最小值用于设置Y轴范围
    final maxValue = spots.isEmpty
        ? 1.0
        : spots.map((s) => s.y).reduce((a, b) => a > b ? a : b);

    // 动态计算Y轴最大值，确保图表能完整显示数据
    // 如果最大值很小（< 0.01），使用更小的范围
    double yAxisMax;
    if (maxValue < 0.01) {
      yAxisMax = 0.01; // 最小显示范围
    } else if (maxValue < 0.1) {
      yAxisMax = (maxValue * 1.2).ceilToDouble() / 10; // 向上取整到0.1
    } else {
      yAxisMax = maxValue * 1.1; // 添加10%的空间
    }

    return LineChart(
      LineChartData(
        minY: 0.0,
        maxY: yAxisMax,
        gridData: FlGridData(show: true),
        titlesData: FlTitlesData(
          leftTitles: AxisTitles(
            sideTitles: SideTitles(
              showTitles: true,
              reservedSize: 60,
              interval: _calculateYAxisInterval(maxValue),
              getTitlesWidget: (value, meta) {
                if (value == 0) return const SizedBox.shrink();
                final unit = _getBestConsumptionUnit(value);
                final convertedValue = (unit['value'] as num).toDouble();
                return Text(
                  '${_formatConsumptionValue(value, convertedValue)}${unit['unit']}',
                  style: const TextStyle(fontSize: 9),
                );
              },
            ),
            axisNameWidget: const Padding(
              padding: EdgeInsets.only(bottom: 10),
              child: Text(
                '每日耗电量',
                style: TextStyle(fontSize: 10, fontWeight: FontWeight.w500),
              ),
            ),
          ),
          bottomTitles: AxisTitles(
            sideTitles: SideTitles(
              showTitles: true,
              reservedSize: 30,
              interval: 5.0,
              getTitlesWidget: (value, meta) {
                final index = value.toInt();
                if (index >= 0 && index < _dailyStats.length) {
                  return Text(
                    _dailyStats[index]['dateString'],
                    style: const TextStyle(fontSize: 10),
                  );
                }
                return const Text('');
              },
            ),
          ),
          rightTitles:
              const AxisTitles(sideTitles: SideTitles(showTitles: false)),
          topTitles:
              const AxisTitles(sideTitles: SideTitles(showTitles: false)),
        ),
        borderData: FlBorderData(show: false),
        lineBarsData: [
          LineChartBarData(
            spots: spots,
            isCurved: true,
            color: const Color(0xFF4A90E2),
            barWidth: 3,
            isStrokeCapRound: true,
            dotData: FlDotData(
              show: spots.length <= 10, // 只在数据点少时显示点
              getDotPainter: (spot, percent, barData, index) {
                return FlDotCirclePainter(
                  radius: 4,
                  color: const Color(0xFF4A90E2),
                  strokeWidth: 2,
                  strokeColor: Colors.white,
                );
              },
            ),
            belowBarData: BarAreaData(
              show: true,
              color: const Color(0xFF4A90E2).withOpacity(0.1),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildMonthlyChart() {
    if (_monthlyStats.isEmpty) {
      return const Center(child: Text('暂无数据'));
    }

    final spots = _monthlyStats.asMap().entries.map((entry) {
      final index = entry.key;
      final data = entry.value;
      return FlSpot(index.toDouble(), (data['consumption'] as num).toDouble());
    }).toList();

    // 计算最大值和最小值用于设置Y轴范围
    final maxValue = spots.isEmpty
        ? 1.0
        : spots.map((s) => s.y).reduce((a, b) => a > b ? a : b);

    // 动态计算Y轴最大值，确保图表能完整显示数据
    // 如果最大值很小（< 0.01），使用更小的范围
    double yAxisMax;
    if (maxValue < 0.01) {
      yAxisMax = 0.01; // 最小显示范围
    } else if (maxValue < 0.1) {
      yAxisMax = (maxValue * 1.2).ceilToDouble() / 10; // 向上取整到0.1
    } else {
      yAxisMax = maxValue * 1.1; // 添加10%的空间
    }

    return LineChart(
      LineChartData(
        minY: 0.0,
        maxY: yAxisMax,
        gridData: FlGridData(show: true),
        titlesData: FlTitlesData(
          leftTitles: AxisTitles(
            sideTitles: SideTitles(
              showTitles: true,
              reservedSize: 60,
              interval: _calculateYAxisInterval(maxValue),
              getTitlesWidget: (value, meta) {
                if (value == 0) return const SizedBox.shrink();
                final unit = _getBestConsumptionUnit(value);
                final convertedValue = (unit['value'] as num).toDouble();
                return Text(
                  '${_formatConsumptionValue(value, convertedValue)}${unit['unit']}',
                  style: const TextStyle(fontSize: 9),
                );
              },
            ),
            axisNameWidget: const Padding(
              padding: EdgeInsets.only(bottom: 10),
              child: Text(
                '月度耗电量',
                style: TextStyle(fontSize: 10, fontWeight: FontWeight.w500),
              ),
            ),
          ),
          bottomTitles: AxisTitles(
            sideTitles: SideTitles(
              showTitles: true,
              reservedSize: 30,
              interval: 2.0,
              getTitlesWidget: (value, meta) {
                final index = value.toInt();
                if (index >= 0 && index < _monthlyStats.length) {
                  return Text(
                    _monthlyStats[index]['dateString'],
                    style: const TextStyle(fontSize: 10),
                  );
                }
                return const Text('');
              },
            ),
          ),
          rightTitles:
              const AxisTitles(sideTitles: SideTitles(showTitles: false)),
          topTitles:
              const AxisTitles(sideTitles: SideTitles(showTitles: false)),
        ),
        borderData: FlBorderData(show: false),
        lineBarsData: [
          LineChartBarData(
            spots: spots,
            isCurved: true,
            color: const Color(0xFF9C27B0),
            barWidth: 3,
            isStrokeCapRound: true,
            dotData: const FlDotData(show: true),
            belowBarData: BarAreaData(
              show: true,
              color: const Color(0xFF9C27B0).withOpacity(0.1),
            ),
          ),
        ],
      ),
    );
  }

  List<Widget> _buildDailyRanking() {
    final sortedDaily = List<Map<String, dynamic>>.from(_dailyStats)
      ..sort((a, b) => (b['consumption'] as num)
          .toDouble()
          .compareTo((a['consumption'] as num).toDouble()));

    return sortedDaily.take(10).map((data) {
      final index = sortedDaily.indexOf(data);
      return Container(
        margin: const EdgeInsets.only(bottom: 8),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: Colors.grey.shade200),
        ),
        child: Row(
          children: [
            Container(
              width: 24,
              height: 24,
              decoration: BoxDecoration(
                color:
                    index < 3 ? const Color(0xFF4A90E2) : Colors.grey.shade300,
                shape: BoxShape.circle,
              ),
              child: Center(
                child: Text(
                  '${index + 1}',
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.bold,
                    color: index < 3 ? Colors.white : Colors.grey.shade600,
                  ),
                ),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                data['dateString'],
                style: const TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ),
            Text(
              '${(data['consumption'] as num).toDouble().toStringAsFixed(2)} mAh',
              style: const TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w600,
                color: Color(0xFF4A90E2),
              ),
            ),
          ],
        ),
      );
    }).toList();
  }

  List<Widget> _buildMonthlyRanking() {
    final sortedMonthly = List<Map<String, dynamic>>.from(_monthlyStats)
      ..sort((a, b) => (b['consumption'] as num)
          .toDouble()
          .compareTo((a['consumption'] as num).toDouble()));

    return sortedMonthly.map((data) {
      final index = sortedMonthly.indexOf(data);
      return Container(
        margin: const EdgeInsets.only(bottom: 8),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: Colors.grey.shade200),
        ),
        child: Row(
          children: [
            Container(
              width: 24,
              height: 24,
              decoration: BoxDecoration(
                color:
                    index < 3 ? const Color(0xFF9C27B0) : Colors.grey.shade300,
                shape: BoxShape.circle,
              ),
              child: Center(
                child: Text(
                  '${index + 1}',
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.bold,
                    color: index < 3 ? Colors.white : Colors.grey.shade600,
                  ),
                ),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                data['dateString'],
                style: const TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ),
            Text(
              '${(data['consumption'] as num).toDouble().toStringAsFixed(2)} mAh',
              style: const TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w600,
                color: Color(0xFF9C27B0),
              ),
            ),
          ],
        ),
      );
    }).toList();
  }

  double _calculateRecentConsumption(int days) {
    if (_dailyStats.isEmpty) return 0.0;

    final recentStats = _dailyStats.take(days);
    return recentStats.fold<double>(
        0.0, (sum, data) => sum + (data['consumption'] as num).toDouble());
  }

  double _calculateAverageDaily() {
    // 使用设备对象中的日均耗电量计算方法（基于有数据的天数）
    final device = monitorController.selectedDevices.firstWhere(
        (d) => d.deviceId == widget.deviceId,
        orElse: () => monitorController.savedDevices
            .firstWhere((d) => d.deviceId == widget.deviceId));

    return device?.averageDailyConsumption ?? 0.0;
  }

  /// 计算Y轴间隔
  double _calculateYAxisInterval(double maxValue) {
    if (maxValue <= 0) return 1.0;

    // 根据最大值确定合适的间隔，确保返回的都是 double 类型
    if (maxValue <= 1) return 0.2;
    if (maxValue <= 5) return 1.0;
    if (maxValue <= 10) return 2.0;
    if (maxValue <= 50) return 10.0;
    if (maxValue <= 100) return 20.0;
    if (maxValue <= 500) return 50.0;
    if (maxValue <= 1000) return 100.0;

    // 对于很大的值，使用动态计算
    final interval = (maxValue / 5).ceilToDouble();
    return interval > 0 ? interval : 1.0;
  }

  /// 获取最佳耗电量单位
  Map<String, dynamic> _getBestConsumptionUnit(double value) {
    if (value < 1) {
      return {'value': 1000, 'unit': 'μAh'}; // 微安时
    } else if (value < 1000) {
      return {'value': 1, 'unit': 'mAh'}; // 毫安时
    } else {
      return {'value': 0.001, 'unit': 'Ah'}; // 安时
    }
  }

  /// 格式化耗电量值
  String _formatConsumptionValue(double value, double conversion) {
    final convertedValue = value * conversion;

    if (convertedValue < 1) {
      return convertedValue.toStringAsFixed(2);
    } else if (convertedValue < 10) {
      return convertedValue.toStringAsFixed(1);
    } else {
      return convertedValue.toStringAsFixed(0);
    }
  }
}
