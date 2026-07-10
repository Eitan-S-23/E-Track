import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:get/get.dart';

/// BLE数据包类型
enum BleDataType {
  advertisement, // 广播包
  scanResponse, // 扫描响应包
}

/// 设备电量数据模型
class DeviceData {
  final String deviceId;
  final String deviceName;
  final DateTime timestamp;
  final double current; // 电流值 (实际单位)
  final String currentUnit; // 电流单位
  final double voltage; // 电压值 (mV)
  final double power; // 功率值 (计算得出)
  final BleDataType dataType; // 数据包类型

  DeviceData({
    required this.deviceId,
    required this.deviceName,
    required this.timestamp,
    required this.current,
    required this.currentUnit,
    required this.voltage,
    required this.power,
    required this.dataType,
  });

  /// 转换为Map用于数据库存储
  Map<String, dynamic> toMap() {
    return {
      'deviceId': deviceId,
      'deviceName': deviceName,
      'timestamp': timestamp.millisecondsSinceEpoch,
      'current': current,
      'currentUnit': currentUnit,
      'voltage': voltage,
      'power': power,
      'dataType': dataType.index,
    };
  }

  /// 从Map创建对象
  factory DeviceData.fromMap(Map<String, dynamic> map) {
    return DeviceData(
      deviceId: map['deviceId'],
      deviceName: map['deviceName'],
      timestamp: DateTime.fromMillisecondsSinceEpoch(map['timestamp']),
      current: map['current'].toDouble(),
      currentUnit: map['currentUnit'],
      voltage: map['voltage'].toDouble(),
      power: map['power'].toDouble(),
      dataType: BleDataType.values[map['dataType'] ?? 0],
    );
  }

  @override
  String toString() {
    return 'DeviceData{deviceId: $deviceId, current: $current$currentUnit, voltage: ${voltage}mV, power: ${power}mW, time: $timestamp}';
  }
}

/// 厂商数据解析器
class ManufacturerDataParser {
  /// 解析0xFF厂商数据
  /// 格式：
  /// - 前2字节：设备ID
  /// - 第3-4字节：电流大小（第4字节为高位）
  /// - 第5字节：电流单位（1=nA, 10=uA, 50=mA, 100=A）
  /// - 第6-7字节：电压大小（第7字节为高位），单位恒定为mV
  static DeviceData? parseManufacturerData(
      String deviceId, String deviceName, List<int> data,
      {BleDataType dataType = BleDataType.advertisement}) {
    if (Platform.isWindows) {
      try {
        if (data.length < 7) {
          debugPrint('数据长度不足，需要至少7字节，实际: ${data.length}');
          return null; // 数据长度不足
        }

        // 打印原始数据用于调试
        debugPrint(
            '解析制造商数据: ${data.map((b) => '0x${b.toRadixString(16).padLeft(2, '0')}').join(' ')}');

        // 解析设备ID (前2字节，小端序)
        int parsedDeviceId = data[0] | (data[1] << 8);
        debugPrint(
            '解析的设备ID: 0x${parsedDeviceId.toRadixString(16).padLeft(4, '0')}');

        // 解析电流值 (第3-4字节，第4字节为高位)
        int currentRaw = data[2] | (data[3] << 8);
        debugPrint('电流原始值: $currentRaw');

        // 解析电流单位 (第5字节)
        int currentUnitCode = data[4];
        String currentUnit;
        double currentMultiplier;

        switch (currentUnitCode) {
          case 1:
            currentUnit = 'nA';
            currentMultiplier = 1e-9; // 转换为A
            break;
          case 10:
            currentUnit = 'uA';
            currentMultiplier = 1e-6; // 转换为A
            break;
          case 50:
            currentUnit = 'mA';
            currentMultiplier = 1e-3; // 转换为A
            break;
          case 100:
            currentUnit = 'A';
            currentMultiplier = 1; // 已经是A
            break;
          default:
            debugPrint('未知的电流单位代码: $currentUnitCode');
            return null; // 未知单位
        }
        debugPrint('电流单位: $currentUnit');

        // 解析电压值 (第6-7字节，第7字节为高位，单位mV)
        int voltageRaw = data[5] | (data[6] << 8);
        double voltage = voltageRaw.toDouble(); // mV
        debugPrint('电压值: $voltage mV');

        // 计算实际电流值
        double current = currentRaw * currentMultiplier;
        debugPrint('电流值: $current A ($currentRaw $currentUnit)');

        // 计算功率 (P = V * I)，电压转换为V
        double power = (voltage / 1000.0) * current * 1000.0; // 转换为mW
        debugPrint('功率值: $power mW');

        return DeviceData(
          deviceId: deviceId,
          deviceName: deviceName,
          timestamp: DateTime.now(),
          current: currentRaw.toDouble(), // 保持原始值用于显示
          currentUnit: currentUnit,
          voltage: voltage,
          power: power,
          dataType: dataType,
        );
      } catch (e) {
        debugPrint('解析厂商数据失败: $e');
        return null;
      }
    } else {
      try {
        if (data.length < 5) {
          debugPrint('数据长度不足，需要至少5字节，实际: ${data.length}');
          return null; // 数据长度不足
        }

        // 打印原始数据用于调试
        debugPrint(
            '解析制造商数据: ${data.map((b) => '0x${b.toRadixString(16).padLeft(2, '0')}').join(' ')}');

        // 解析电流值 (第1-2字节，第2字节为高位)
        int currentRaw = data[0] | (data[1] << 8);
        debugPrint('电流原始值: $currentRaw');

        // 解析电流单位 (第3字节)
        int currentUnitCode = data[2];
        String currentUnit;
        double currentMultiplier;

        switch (currentUnitCode) {
          case 1:
            currentUnit = 'nA';
            currentMultiplier = 1e-9; // 转换为A
            break;
          case 10:
            currentUnit = 'uA';
            currentMultiplier = 1e-6; // 转换为A
            break;
          case 50:
            currentUnit = 'mA';
            currentMultiplier = 1e-3; // 转换为A
            break;
          case 100:
            currentUnit = 'A';
            currentMultiplier = 1; // 已经是A
            break;
          default:
            debugPrint('未知的电流单位代码: $currentUnitCode');
            return null; // 未知单位
        }
        debugPrint('电流单位: $currentUnit');

        // 解析电压值 (第4-5字节，第5字节为高位，单位mV)
        int voltageRaw = data[3] | (data[4] << 8);
        double voltage = voltageRaw.toDouble(); // mV
        debugPrint('电压值: $voltage mV');

        // 计算实际电流值
        double current = currentRaw * currentMultiplier;
        debugPrint('电流值: $current A ($currentRaw $currentUnit)');

        // 计算功率 (P = V * I)，电压转换为V
        double power = (voltage / 1000.0) * current * 1000.0; // 转换为mW
        debugPrint('功率值: $power mW');

        return DeviceData(
          deviceId: deviceId,
          deviceName: deviceName,
          timestamp: DateTime.now(),
          current: currentRaw.toDouble(), // 保持原始值用于显示
          currentUnit: currentUnit,
          voltage: voltage,
          power: power,
          dataType: dataType,
        );
      } catch (e) {
        debugPrint('解析厂商数据失败: $e');
        return null;
      }
    }
  }

  /// 计算功率消耗 (mAh) - 使用梯形积分法提高精度
  static double calculatePowerConsumption(List<DeviceData> dataList) {
    if (dataList.length < 2) return 0.0;

    double totalConsumption = 0.0;

    for (int i = 1; i < dataList.length; i++) {
      DeviceData current = dataList[i];
      DeviceData previous = dataList[i - 1];

      // 计算时间差(小时)
      double timeDiffHours =
          current.timestamp.difference(previous.timestamp).inMilliseconds /
              (1000.0 * 60.0 * 60.0);

      // 转换电流为mA
      double currentInMA =
          _convertToMilliAmps(current.current, current.currentUnit);
      double previousInMA =
          _convertToMilliAmps(previous.current, previous.currentUnit);

      // 使用梯形积分法计算平均电流
      double avgCurrentMA = (currentInMA + previousInMA) / 2.0;

      // 计算消耗量 (mAh)
      totalConsumption += avgCurrentMA * timeDiffHours;
    }

    return totalConsumption;
  }

  /// 转换电流为mA
  static double _convertToMilliAmps(double current, String unit) {
    switch (unit) {
      case 'nA':
        return current / 1000000.0;
      case 'uA':
        return current / 1000.0;
      case 'mA':
        return current;
      case 'A':
        return current * 1000.0;
      default:
        return 0.0;
    }
  }
}

/// 选中设备信息
class SelectedDevice {
  final String deviceId;
  String deviceName; // 改为可变的，以便在扫描时更新
  final List<DeviceData> dataHistory;
  var isMonitoring = false.obs;

  // 每日耗电量统计数组（最近365天）
  final List<double?> _dailyConsumptionArray = List.filled(365, null);

  // 月度耗电量统计数组（最近12个月）
  final List<double?> _monthlyConsumptionArray = List.filled(12, null);

  // 当前统计的日期索引（用于每日数组）
  int _currentDayIndex = 0;

  // 当前统计的月份索引（用于月度数组）
  int _currentMonthIndex = 0;

  // 本次会话耗电量（软件重启后清零）
  double _sessionConsumption = 0.0;

  SelectedDevice({
    required this.deviceId,
    required this.deviceName,
    List<DeviceData>? dataHistory,
    bool monitoring = false,
    bool loadFromDatabase = false, // 新增参数，表示是否从数据库加载
  }) : dataHistory = dataHistory ?? [] {
    isMonitoring.value = monitoring;
    // 如果不是从数据库加载，则清空累计耗电量（重启后重置）
    // 如果是从数据库加载，则保持现有的统计数组数据
    if (!loadFromDatabase) {
      clearAllConsumptionStats();
      _sessionConsumption = 0.0; // 重启后清零本次会话耗电量
    }
  }

  /// 添加新数据（带去重功能）
  void addData(DeviceData data, {bool updateConsumption = true}) {
    // 检查是否是重复数据
    if (dataHistory.isNotEmpty) {
      final latestData = dataHistory.last;

      // 如果时间间隔小于1秒且数据完全相同，则跳过
      final timeDiff =
          data.timestamp.difference(latestData.timestamp).inMilliseconds;
      if (timeDiff < 1000 && _isDataIdentical(data, latestData)) {
        debugPrint(
            '跳过重复数据: ${data.deviceName} - ${data.current}${data.currentUnit}');
        return;
      }

      // 如果时间间隔小于500毫秒，无论数据是否相同都跳过（防止过于频繁的数据）
      if (timeDiff < 500) {
        debugPrint('跳过过于频繁的数据: ${data.deviceName} - 间隔${timeDiff}ms');
        return;
      }
    }

    dataHistory.add(data);
    // 限制历史数据数量，避免内存过大
    if (dataHistory.length > 86400) {
      dataHistory.removeAt(0);
    }

    // 更新每日和月度耗电量统计（仅在需要时更新）
    if (updateConsumption) {
      _updateDailyConsumptionArray(data);
      _updateMonthlyConsumptionArray(data);
      _updateSessionConsumption(data);
    }
  }

  /// 检查两个数据是否完全相同
  bool _isDataIdentical(DeviceData data1, DeviceData data2) {
    return data1.current == data2.current &&
        data1.currentUnit == data2.currentUnit &&
        data1.voltage == data2.voltage &&
        data1.power == data2.power;
  }

  /// 获取最新数据
  DeviceData? get latestData =>
      dataHistory.isNotEmpty ? dataHistory.last : null;

  /// 获取功耗
  double get powerConsumption =>
      ManufacturerDataParser.calculatePowerConsumption(dataHistory);

  /// 获取本次会话耗电量（软件重启后清零）
  double get sessionConsumption => _sessionConsumption;

  /// 更新每日耗电量统计数组
  void _updateDailyConsumptionArray(DeviceData newData) {
    // 获取当前日期（只考虑年月日）
    final today = DateTime(
        newData.timestamp.year, newData.timestamp.month, newData.timestamp.day);

    // 计算今天在数组中的索引（相对于今天，向后365天）
    final daysSinceEpoch = today.difference(DateTime(2020, 1, 1)).inDays;
    final arrayIndex = daysSinceEpoch % 365;

    // 如果有前一个数据点，计算耗电量增量
    if (dataHistory.length >= 2) {
      final previousData = dataHistory[dataHistory.length - 2];

      // 计算时间差（小时）
      final timeDiffHours =
          newData.timestamp.difference(previousData.timestamp).inMilliseconds /
              (1000.0 * 60.0 * 60.0);

      // 如果时间差合理（避免异常数据）
      if (timeDiffHours > 0 && timeDiffHours < 24) {
        // 转换电流为mA
        final currentInMA =
            _convertCurrentToMA(newData.current, newData.currentUnit);
        final previousInMA =
            _convertCurrentToMA(previousData.current, previousData.currentUnit);

        // 使用梯形积分法计算平均电流
        final avgCurrentMA = (currentInMA + previousInMA) / 2.0;

        // 计算耗电量增量（mAh）
        final consumptionIncrement = avgCurrentMA * timeDiffHours;

        // 更新或累加当天的耗电量
        final currentValue = _dailyConsumptionArray[arrayIndex] ?? 0.0;
        _dailyConsumptionArray[arrayIndex] =
            currentValue + consumptionIncrement;
      }
    }
  }

  /// 更新月度耗电量统计数组
  void _updateMonthlyConsumptionArray(DeviceData newData) {
    // 获取当前月份
    final currentMonth =
        DateTime(newData.timestamp.year, newData.timestamp.month);

    // 计算月份在数组中的索引（相对于当前月份，向后12个月）
    final monthsSinceEpoch =
        (currentMonth.year - 2020) * 12 + (currentMonth.month - 1);
    final arrayIndex = monthsSinceEpoch % 12;

    // 如果有前一个数据点，计算耗电量增量
    if (dataHistory.length >= 2) {
      final previousData = dataHistory[dataHistory.length - 2];

      // 计算时间差（小时）
      final timeDiffHours =
          newData.timestamp.difference(previousData.timestamp).inMilliseconds /
              (1000.0 * 60.0 * 60.0);

      // 如果时间差合理（避免异常数据）
      if (timeDiffHours > 0 && timeDiffHours < 24 * 31) {
        // 一个月内
        // 转换电流为mA
        final currentInMA =
            _convertCurrentToMA(newData.current, newData.currentUnit);
        final previousInMA =
            _convertCurrentToMA(previousData.current, previousData.currentUnit);

        // 使用梯形积分法计算平均电流
        final avgCurrentMA = (currentInMA + previousInMA) / 2.0;

        // 计算耗电量增量（mAh）
        final consumptionIncrement = avgCurrentMA * timeDiffHours;

        // 更新或累加当月的耗电量
        final currentValue = _monthlyConsumptionArray[arrayIndex] ?? 0.0;
        _monthlyConsumptionArray[arrayIndex] =
            currentValue + consumptionIncrement;
      }
    }
  }

  /// 更新本次会话耗电量（软件重启后清零）
  void _updateSessionConsumption(DeviceData newData) {
    // 如果有前一个数据点，计算耗电量增量
    if (dataHistory.length >= 2) {
      final previousData = dataHistory[dataHistory.length - 2];

      // 计算时间差（小时）
      final timeDiffHours =
          newData.timestamp.difference(previousData.timestamp).inMilliseconds /
              (1000.0 * 60.0 * 60.0);

      // 如果时间差合理（避免异常数据）
      if (timeDiffHours > 0 && timeDiffHours < 24) {
        // 转换电流为mA
        final currentInMA =
            _convertCurrentToMA(newData.current, newData.currentUnit);
        final previousInMA =
            _convertCurrentToMA(previousData.current, previousData.currentUnit);

        // 使用梯形积分法计算平均电流
        final avgCurrentMA = (currentInMA + previousInMA) / 2.0;

        // 计算耗电量增量（mAh）
        final consumptionIncrement = avgCurrentMA * timeDiffHours;

        // 累加到本次会话耗电量
        _sessionConsumption += consumptionIncrement;
      }
    }
  }

  /// 转换电流为mA
  double _convertCurrentToMA(double current, String unit) {
    switch (unit) {
      case 'nA':
        return current / 1000000.0;
      case 'uA':
        return current / 1000.0;
      case 'mA':
        return current;
      case 'A':
        return current * 1000.0;
      default:
        return 0.0;
    }
  }

  /// 获取每日耗电量统计数组
  List<double?> get dailyConsumptionArray =>
      List.unmodifiable(_dailyConsumptionArray);

  /// 获取月度耗电量统计数组
  List<double?> get monthlyConsumptionArray =>
      List.unmodifiable(_monthlyConsumptionArray);

  /// 获取指定日期的每日耗电量
  double? getDailyConsumption(DateTime date) {
    final daysSinceEpoch = date.difference(DateTime(2020, 1, 1)).inDays;
    final arrayIndex = daysSinceEpoch % 365;
    return _dailyConsumptionArray[arrayIndex];
  }

  /// 获取最近N天的每日耗电量统计（用于图表显示）
  List<Map<String, dynamic>> getDailyConsumptionStats({int days = 30}) {
    final List<Map<String, dynamic>> stats = [];
    final now = DateTime.now();

    for (int i = 0; i < days && i < 365; i++) {
      final date = now.subtract(Duration(days: i));
      final daysSinceEpoch = date.difference(DateTime(2020, 1, 1)).inDays;
      final arrayIndex = daysSinceEpoch % 365;
      final consumption = _dailyConsumptionArray[arrayIndex];

      if (consumption != null && consumption > 0) {
        stats.add({
          'date': date,
          'consumption': consumption,
          'dateString':
              '${date.month.toString().padLeft(2, '0')}-${date.day.toString().padLeft(2, '0')}',
        });
      }
    }

    return stats.reversed.toList(); // 按时间顺序排列
  }

  /// 获取月度耗电量统计（用于图表显示）
  List<Map<String, dynamic>> getMonthlyConsumptionStats({int months = 12}) {
    final List<Map<String, dynamic>> stats = [];
    final now = DateTime.now();

    for (int i = 0; i < months && i < 12; i++) {
      final month = DateTime(now.year, now.month - i, 1);
      final monthsSinceEpoch = (month.year - 2020) * 12 + (month.month - 1);
      final arrayIndex = monthsSinceEpoch % 12;
      final consumption = _monthlyConsumptionArray[arrayIndex];

      if (consumption != null && consumption > 0) {
        stats.add({
          'date': month,
          'consumption': consumption,
          'dateString': '${month.month}月',
        });
      }
    }

    return stats.reversed.toList(); // 按时间顺序排列
  }

  /// 获取近一年总耗电量（月度数组累加）
  double get totalConsumptionOneYear {
    return _monthlyConsumptionArray.fold(
        0.0, (sum, value) => sum + (value ?? 0.0));
  }

  /// 获取有数据的天数
  int get daysWithData {
    return _dailyConsumptionArray
        .where((value) => value != null && value! > 0)
        .length;
  }

  /// 获取日均耗电量（基于有数据的天数）
  double get averageDailyConsumption {
    final days = daysWithData;
    if (days == 0) return 0.0;

    final totalConsumption =
        _dailyConsumptionArray.fold(0.0, (sum, value) => sum + (value ?? 0.0));
    return totalConsumption / days;
  }

  /// 清空每日耗电量统计数组
  void clearDailyConsumptionStats() {
    for (int i = 0; i < _dailyConsumptionArray.length; i++) {
      _dailyConsumptionArray[i] = null;
    }
  }

  /// 清空月度耗电量统计数组
  void clearMonthlyConsumptionStats() {
    for (int i = 0; i < _monthlyConsumptionArray.length; i++) {
      _monthlyConsumptionArray[i] = null;
    }
  }

  /// 清空所有统计数组
  void clearAllConsumptionStats() {
    clearDailyConsumptionStats();
    clearMonthlyConsumptionStats();
    _sessionConsumption = 0.0; // 清零本次会话耗电量
  }

  /// 重置本次会话耗电量（用于软件重启时清零）
  void resetSessionConsumption() {
    _sessionConsumption = 0.0;
  }

  /// 从数据库加载每日耗电量统计数组
  void loadDailyConsumptionArray(List<double?> dailyArray) {
    if (dailyArray.length == 365) {
      for (int i = 0; i < 365; i++) {
        _dailyConsumptionArray[i] = dailyArray[i];
      }
    }
  }

  /// 从数据库加载月度耗电量统计数组
  void loadMonthlyConsumptionArray(List<double?> monthlyArray) {
    if (monthlyArray.length == 12) {
      for (int i = 0; i < 12; i++) {
        _monthlyConsumptionArray[i] = monthlyArray[i];
      }
    }
  }

  /// 保存每日耗电量统计数组到数据库（简化版本，实际应该通过服务层调用）
  Future<void> saveDailyConsumptionArrayToDb() async {
    // 这里应该通过DatabaseService来保存，但为了简化，直接返回
    // 实际实现时应该调用DatabaseService的方法
  }

  /// 保存月度耗电量统计数组到数据库（简化版本，实际应该通过服务层调用）
  Future<void> saveMonthlyConsumptionArrayToDb() async {
    // 这里应该通过DatabaseService来保存，但为了简化，直接返回
    // 实际实现时应该调用DatabaseService的方法
  }

  /// 转换为Map
  Map<String, dynamic> toMap() {
    return {
      'deviceId': deviceId,
      'deviceName': deviceName,
      'isMonitoring': isMonitoring.value ? 1 : 0,
    };
  }

  /// 从Map创建
  factory SelectedDevice.fromMap(Map<String, dynamic> map,
      {bool loadFromDatabase = false}) {
    return SelectedDevice(
      deviceId: map['deviceId'],
      deviceName: map['deviceName'],
      monitoring: map['isMonitoring'] == 1,
      loadFromDatabase: loadFromDatabase,
    );
  }
}

/// 每日耗电量统计数据模型
class DailyPowerConsumption {
  final String deviceId;
  final DateTime date; // 统计日期（只包含年月日，时分秒为0）
  final double consumption; // 当日耗电量 (mAh)
  final int dataPoints; // 当日数据点数量

  DailyPowerConsumption({
    required this.deviceId,
    required this.date,
    required this.consumption,
    required this.dataPoints,
  });

  /// 获取日期的唯一键（用于比较）
  String get dateKey =>
      '${date.year}-${date.month.toString().padLeft(2, '0')}-${date.day.toString().padLeft(2, '0')}';

  /// 转换为Map用于数据库存储
  Map<String, dynamic> toMap() {
    return {
      'deviceId': deviceId,
      'date': date.millisecondsSinceEpoch,
      'consumption': consumption,
      'dataPoints': dataPoints,
    };
  }

  /// 从Map创建对象
  factory DailyPowerConsumption.fromMap(Map<String, dynamic> map) {
    return DailyPowerConsumption(
      deviceId: map['deviceId'],
      date: DateTime.fromMillisecondsSinceEpoch(map['date']),
      consumption: map['consumption'].toDouble(),
      dataPoints: map['dataPoints'],
    );
  }

  @override
  String toString() {
    return 'DailyPowerConsumption{deviceId: $deviceId, date: $dateKey, consumption: ${consumption.toStringAsFixed(2)} mAh, dataPoints: $dataPoints}';
  }
}

/// 月度耗电量统计数据模型
class MonthlyPowerConsumption {
  final String deviceId;
  final int year; // 年份
  final int monthIndex; // 月份索引（0-11，对应1-12月）
  final double consumption; // 当月耗电量 (mAh)
  final int dataPoints; // 当月数据点数量

  MonthlyPowerConsumption({
    required this.deviceId,
    required this.year,
    required this.monthIndex,
    required this.consumption,
    required this.dataPoints,
  });

  /// 获取月份的唯一键（用于比较）
  String get monthKey =>
      '${year}-${(monthIndex + 1).toString().padLeft(2, '0')}';

  /// 转换为Map用于数据库存储
  Map<String, dynamic> toMap() {
    return {
      'deviceId': deviceId,
      'year': year,
      'monthIndex': monthIndex,
      'consumption': consumption,
      'dataPoints': dataPoints,
    };
  }

  /// 从Map创建对象
  factory MonthlyPowerConsumption.fromMap(Map<String, dynamic> map) {
    return MonthlyPowerConsumption(
      deviceId: map['deviceId'],
      year: map['year'],
      monthIndex: map['monthIndex'],
      consumption: map['consumption'].toDouble(),
      dataPoints: map['dataPoints'],
    );
  }

  @override
  String toString() {
    return 'MonthlyPowerConsumption{deviceId: $deviceId, month: $monthKey, consumption: ${consumption.toStringAsFixed(2)} mAh, dataPoints: $dataPoints}';
  }
}
