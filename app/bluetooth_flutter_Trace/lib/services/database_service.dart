import 'package:flutter/foundation.dart';
import 'package:sqflite/sqflite.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';
import 'package:path/path.dart';
import '../models/device_data.dart';
import '../models/device_settings.dart';
import '../models/ride_models.dart';

class DatabaseService {
  static final DatabaseService _instance = DatabaseService._internal();
  factory DatabaseService() => _instance;
  DatabaseService._internal();

  static Database? _database;

  Future<Database> get database async {
    if (_database != null) return _database!;
    _database = await _initDatabase();
    return _database!;
  }

  Future<Database> _initDatabase() async {
    // FFI已在main.dart中初始化，这里不需要重复初始化
    String path = join(await getDatabasesPath(), 'ble_monitor.db');

    return await openDatabase(
      path,
      version: 6, // 新增自定义按钮表
      onCreate: _createTables,
      onUpgrade: _upgradeDatabase,
      onOpen: _createRideTables,
    );
  }

  Future<void> _upgradeDatabase(
      Database db, int oldVersion, int newVersion) async {
    if (oldVersion < 2) {
      // 添加新的字段和表
      await db.execute('''
        ALTER TABLE device_data ADD COLUMN powerConsumption REAL DEFAULT 0.0
      ''');

      // 添加设备配置表
      await db.execute('''
        CREATE TABLE IF NOT EXISTS device_settings (
          deviceId TEXT PRIMARY KEY,
          currentThreshold REAL DEFAULT 1000.0,
          voltageThreshold REAL DEFAULT 24.0,
          powerThreshold REAL DEFAULT 100.0,
          powerConsumptionThreshold REAL DEFAULT 1000.0,
          currentUnit TEXT DEFAULT 'mA',
          voltageUnit TEXT DEFAULT 'V',
          powerUnit TEXT DEFAULT 'W',
          powerConsumptionUnit TEXT DEFAULT 'mAh',
          alertEnabled INTEGER DEFAULT 1,
          alertType INTEGER DEFAULT 0,
          customSoundPath TEXT,
          FOREIGN KEY (deviceId) REFERENCES devices (deviceId)
        )
      ''');

      // 添加扫描设置表
      await db.execute('''
        CREATE TABLE IF NOT EXISTS scan_settings (
          id INTEGER PRIMARY KEY,
          scanInterval INTEGER DEFAULT 1000
        )
      ''');

      // 插入默认扫描设置
      await db.insert('scan_settings', {'id': 1, 'scanInterval': 1000});
    }

    if (oldVersion < 3) {
      // 添加每日耗电量统计表
      await db.execute('''
        CREATE TABLE IF NOT EXISTS daily_power_consumption (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          deviceId TEXT NOT NULL,
          date INTEGER NOT NULL, -- 日期的毫秒时间戳（只包含年月日，时分秒为0）
          consumption REAL NOT NULL DEFAULT 0.0,
          dataPoints INTEGER NOT NULL DEFAULT 0,
          createdAt INTEGER NOT NULL,
          updatedAt INTEGER NOT NULL,
          FOREIGN KEY (deviceId) REFERENCES devices (deviceId),
          UNIQUE(deviceId, date)
        )
      ''');

      // 创建索引
      await db.execute('''
        CREATE INDEX IF NOT EXISTS idx_daily_consumption_device_date ON daily_power_consumption (deviceId, date)
      ''');

      await db.execute('''
        CREATE INDEX IF NOT EXISTS idx_daily_consumption_date ON daily_power_consumption (date)
      ''');
    }

    if (oldVersion < 4) {
      // 添加月度耗电量统计表
      await db.execute('''
        CREATE TABLE IF NOT EXISTS monthly_power_consumption (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          deviceId TEXT NOT NULL,
          monthIndex INTEGER NOT NULL, -- 月份索引（0-11，对应1-12月）
          year INTEGER NOT NULL, -- 年份
          consumption REAL NOT NULL DEFAULT 0.0,
          dataPoints INTEGER NOT NULL DEFAULT 0,
          createdAt INTEGER NOT NULL,
          updatedAt INTEGER NOT NULL,
          FOREIGN KEY (deviceId) REFERENCES devices (deviceId),
          UNIQUE(deviceId, year, monthIndex)
        )
      ''');

      // 创建索引
      await db.execute('''
        CREATE INDEX IF NOT EXISTS idx_monthly_consumption_device_month ON monthly_power_consumption (deviceId, year, monthIndex)
      ''');

      await db.execute('''
        CREATE INDEX IF NOT EXISTS idx_monthly_consumption_year_month ON monthly_power_consumption (year, monthIndex)
      ''');
    }

    if (oldVersion < 5) {
      // 添加自定义铃声路径字段
      await db.execute('''
        ALTER TABLE device_settings ADD COLUMN customSoundPath TEXT
      ''');
    }

    if (oldVersion < 6) {
      // 创建自定义按钮表（全局共享，不区分设备）
      await db.execute('''
        CREATE TABLE IF NOT EXISTS custom_buttons (
          id TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          iconCode INTEGER NOT NULL,
          colorValue INTEGER NOT NULL,
          isHex INTEGER NOT NULL,
          payload TEXT NOT NULL,
          createdAt INTEGER,
          updatedAt INTEGER
        )
      ''');
    }
  }

  Future<void> _createTables(Database db, int version) async {
    // 创建设备表
    await db.execute('''
      CREATE TABLE devices (
        deviceId TEXT PRIMARY KEY,
        deviceName TEXT NOT NULL,
        isMonitoring INTEGER NOT NULL DEFAULT 0,
        createdAt INTEGER NOT NULL,
        updatedAt INTEGER NOT NULL
      )
    ''');

    // 创建设备数据表
    await db.execute('''
      CREATE TABLE device_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        deviceId TEXT NOT NULL,
        deviceName TEXT NOT NULL,
        timestamp INTEGER NOT NULL,
        current REAL NOT NULL,
        currentUnit TEXT NOT NULL,
        voltage REAL NOT NULL,
        power REAL NOT NULL,
        powerConsumption REAL DEFAULT 0.0,
        dataType INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (deviceId) REFERENCES devices (deviceId)
      )
    ''');

    // 创建索引
    await db.execute('''
      CREATE INDEX idx_device_data_device_id ON device_data (deviceId)
    ''');

    await db.execute('''
      CREATE INDEX idx_device_data_timestamp ON device_data (timestamp)
    ''');

    // 创建设备配置表
    await db.execute('''
      CREATE TABLE IF NOT EXISTS device_settings (
        deviceId TEXT PRIMARY KEY,
        currentThreshold REAL DEFAULT 1000.0,
        voltageThreshold REAL DEFAULT 24.0,
        powerThreshold REAL DEFAULT 100.0,
        powerConsumptionThreshold REAL DEFAULT 1000.0,
        currentUnit TEXT DEFAULT 'mA',
        voltageUnit TEXT DEFAULT 'V',
        powerUnit TEXT DEFAULT 'W',
        powerConsumptionUnit TEXT DEFAULT 'mAh',
        alertEnabled INTEGER DEFAULT 1,
        alertType INTEGER DEFAULT 0,
        customSoundPath TEXT,
        FOREIGN KEY (deviceId) REFERENCES devices (deviceId)
      )
    ''');

    // 创建扫描设置表
    await db.execute('''
      CREATE TABLE IF NOT EXISTS scan_settings (
        id INTEGER PRIMARY KEY,
        scanInterval INTEGER DEFAULT 1000
      )
    ''');

    // 插入默认扫描设置
    await db.insert('scan_settings', {'id': 1, 'scanInterval': 1000});

    // 创建设备每日耗电量统计表
    await db.execute('''
      CREATE TABLE IF NOT EXISTS daily_power_consumption (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        deviceId TEXT NOT NULL,
        date INTEGER NOT NULL, -- 日期的毫秒时间戳（只包含年月日，时分秒为0）
        consumption REAL NOT NULL DEFAULT 0.0,
        dataPoints INTEGER NOT NULL DEFAULT 0,
        createdAt INTEGER NOT NULL,
        updatedAt INTEGER NOT NULL,
        FOREIGN KEY (deviceId) REFERENCES devices (deviceId),
        UNIQUE(deviceId, date)
      )
    ''');

    // 创建索引
    await db.execute('''
      CREATE INDEX IF NOT EXISTS idx_daily_consumption_device_date ON daily_power_consumption (deviceId, date)
    ''');

    await db.execute('''
      CREATE INDEX IF NOT EXISTS idx_daily_consumption_date ON daily_power_consumption (date)
    ''');

    // 创建设备月度耗电量统计表
    await db.execute('''
      CREATE TABLE IF NOT EXISTS monthly_power_consumption (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        deviceId TEXT NOT NULL,
        monthIndex INTEGER NOT NULL, -- 月份索引（0-11，对应1-12月）
        year INTEGER NOT NULL, -- 年份
        consumption REAL NOT NULL DEFAULT 0.0,
        dataPoints INTEGER NOT NULL DEFAULT 0,
        createdAt INTEGER NOT NULL,
        updatedAt INTEGER NOT NULL,
        FOREIGN KEY (deviceId) REFERENCES devices (deviceId),
        UNIQUE(deviceId, year, monthIndex)
      )
    ''');

    // 创建索引
    await db.execute('''
      CREATE INDEX IF NOT EXISTS idx_monthly_consumption_device_month ON monthly_power_consumption (deviceId, year, monthIndex)
    ''');

    await db.execute('''
      CREATE INDEX IF NOT EXISTS idx_monthly_consumption_year_month ON monthly_power_consumption (year, monthIndex)
    ''');

    // 创建自定义按钮表
    await db.execute('''
      CREATE TABLE IF NOT EXISTS custom_buttons (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        iconCode INTEGER NOT NULL,
        colorValue INTEGER NOT NULL,
        isHex INTEGER NOT NULL,
        payload TEXT NOT NULL,
        createdAt INTEGER,
        updatedAt INTEGER
      )
    ''');

    await _createRideTables(db);
  }

  Future<void> _createRideTables(Database db) async {
    await db.execute('''
      CREATE TABLE IF NOT EXISTS rides (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        deviceId TEXT,
        deviceName TEXT,
        startTime INTEGER NOT NULL,
        endTime INTEGER NOT NULL,
        durationSeconds INTEGER NOT NULL,
        distanceKm REAL NOT NULL DEFAULT 0.0,
        avgSpeedKmh REAL NOT NULL DEFAULT 0.0,
        maxSpeedKmh REAL NOT NULL DEFAULT 0.0,
        totalClimbM REAL NOT NULL DEFAULT 0.0,
        createdAt INTEGER NOT NULL
      )
    ''');

    await db.execute('''
      CREATE TABLE IF NOT EXISTS ride_points (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rideId INTEGER NOT NULL,
        timestamp INTEGER NOT NULL,
        latitude REAL NOT NULL,
        longitude REAL NOT NULL,
        speedKmh REAL NOT NULL DEFAULT 0.0,
        altitudeM REAL NOT NULL DEFAULT 0.0,
        FOREIGN KEY (rideId) REFERENCES rides (id) ON DELETE CASCADE
      )
    ''');

    await db.execute('''
      CREATE INDEX IF NOT EXISTS idx_rides_start_time ON rides (startTime DESC)
    ''');

    await db.execute('''
      CREATE INDEX IF NOT EXISTS idx_ride_points_ride_time ON ride_points (rideId, timestamp ASC)
    ''');
  }

  /// 保存或更新设备
  Future<void> saveDevice(SelectedDevice device) async {
    final db = await database;
    final now = DateTime.now().millisecondsSinceEpoch;

    await db.insert(
      'devices',
      {
        'deviceId': device.deviceId,
        'deviceName': device.deviceName,
        'isMonitoring': device.isMonitoring.value ? 1 : 0,
        'createdAt': now,
        'updatedAt': now,
      },
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  /// 获取所有保存的设备
  Future<List<SelectedDevice>> getSavedDevices() async {
    final db = await database;
    final List<Map<String, dynamic>> maps = await db.query('devices');

    return List.generate(maps.length, (i) {
      return SelectedDevice.fromMap(maps[i], loadFromDatabase: true);
    });
  }

  /// 删除设备
  Future<void> deleteDevice(String deviceId) async {
    final db = await database;
    await db.transaction((txn) async {
      // 删除设备数据
      await txn.delete(
        'device_data',
        where: 'deviceId = ?',
        whereArgs: [deviceId],
      );
      // 删除设备
      await txn.delete(
        'devices',
        where: 'deviceId = ?',
        whereArgs: [deviceId],
      );
    });
  }

  /// 更新设备名称
  Future<void> updateDeviceName(String deviceId, String newName) async {
    final db = await database;
    await db.update(
      'devices',
      {
        'deviceName': newName,
        'updatedAt': DateTime.now().millisecondsSinceEpoch,
      },
      where: 'deviceId = ?',
      whereArgs: [deviceId],
    );
    debugPrint('数据库更新设备名称: $deviceId -> $newName');
  }

  /// 保存设备数据
  Future<void> saveDeviceData(DeviceData data) async {
    final db = await database;
    await db.insert(
      'device_data',
      data.toMap(),
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  /// 批量保存设备数据（替换该设备的所有历史数据）
  /// 警告：此方法会删除该设备的所有现有数据！
  Future<void> saveDeviceDataBatch(List<DeviceData> dataList) async {
    if (dataList.isEmpty) return;

    final db = await database;
    final deviceId = dataList.first.deviceId;

    final batch = db.batch();

    // 先删除该设备的所有历史数据，确保数据一致性
    batch.delete(
      'device_data',
      where: 'deviceId = ?',
      whereArgs: [deviceId],
    );

    // 然后批量插入新数据
    for (var data in dataList) {
      batch.insert(
        'device_data',
        data.toMap(),
        conflictAlgorithm: ConflictAlgorithm.replace,
      );
    }

    await batch.commit(noResult: true);
    debugPrint('批量保存 ${dataList.length} 条数据到设备 $deviceId（已替换该设备的历史数据）');
  }

  /// 批量追加设备数据（不删除现有数据，只添加新数据）
  /// 这是更安全的保存方法，用于追加新的监控数据
  Future<void> appendDeviceDataBatch(List<DeviceData> dataList) async {
    if (dataList.isEmpty) return;

    final db = await database;
    final deviceId = dataList.first.deviceId;

    // 使用事务确保数据一致性
    await db.transaction((txn) async {
      final batch = txn.batch();

      // 批量插入数据，使用IGNORE避免重复
      for (var data in dataList) {
        batch.insert(
          'device_data',
          data.toMap(),
          conflictAlgorithm: ConflictAlgorithm.ignore, // 忽略重复数据
        );
      }

      await batch.commit(noResult: true);
    });

    debugPrint('批量追加 ${dataList.length} 条数据到设备 $deviceId');
  }

  /// 获取设备数据总数
  Future<int> getDeviceDataCount(String deviceId) async {
    final db = await database;
    final result = await db.rawQuery(
        'SELECT COUNT(*) as count FROM device_data WHERE deviceId = ?',
        [deviceId]);
    return Sqflite.firstIntValue(result) ?? 0;
  }

  /// 带偏移量的获取设备数据
  Future<List<DeviceData>> getDeviceDataWithOffset(String deviceId,
      {required int skip, required int limit}) async {
    final db = await database;

    final String sql = '''
      SELECT * FROM device_data 
      WHERE deviceId = ? 
      ORDER BY timestamp ASC 
      LIMIT ? OFFSET ?
    ''';

    final List<Map<String, dynamic>> maps =
        await db.rawQuery(sql, [deviceId, limit, skip]);

    return List.generate(maps.length, (i) {
      return DeviceData.fromMap(maps[i]);
    });
  }

  /// 获取设备数据的最新N条记录
  Future<List<DeviceData>> getLatestDeviceData(
      String deviceId, int limit) async {
    final db = await database;

    final String sql = '''
      SELECT * FROM device_data 
      WHERE deviceId = ? 
      ORDER BY timestamp DESC 
      LIMIT ?
    ''';

    final List<Map<String, dynamic>> maps =
        await db.rawQuery(sql, [deviceId, limit]);

    // 将结果按时间顺序重新排列
    final result = List.generate(maps.length, (i) {
      return DeviceData.fromMap(maps[i]);
    });

    return result.reversed.toList();
  }

  /// 获取设备的历史数据
  Future<List<DeviceData>> getDeviceData(String deviceId,
      {int? limit, DateTime? startTime, DateTime? endTime}) async {
    final db = await database;

    // 使用原生SQL查询以避免SQLite的默认限制
    String sql = 'SELECT * FROM device_data WHERE deviceId = ?';
    List<dynamic> args = [deviceId];

    if (startTime != null) {
      sql += ' AND timestamp >= ?';
      args.add(startTime.millisecondsSinceEpoch);
    }

    if (endTime != null) {
      sql += ' AND timestamp <= ?';
      args.add(endTime.millisecondsSinceEpoch);
    }

    sql += ' ORDER BY timestamp ASC';

    if (limit != null) {
      sql += ' LIMIT $limit';
    }

    final List<Map<String, dynamic>> maps = await db.rawQuery(sql, args);

    return List.generate(maps.length, (i) {
      return DeviceData.fromMap(maps[i]);
    });
  }

  /// 获取设备最新数据（单条记录）
  Future<DeviceData?> getLatestSingleDeviceData(String deviceId) async {
    final db = await database;
    final List<Map<String, dynamic>> maps = await db.query(
      'device_data',
      where: 'deviceId = ?',
      whereArgs: [deviceId],
      orderBy: 'timestamp DESC',
      limit: 1,
    );

    if (maps.isNotEmpty) {
      return DeviceData.fromMap(maps.first);
    }
    return null;
  }

  /// 获取指定时间范围内的数据统计
  Future<Map<String, dynamic>> getDataStatistics(
      String deviceId, DateTime startTime, DateTime endTime) async {
    final db = await database;

    final List<Map<String, dynamic>> result = await db.rawQuery('''
      SELECT 
        COUNT(*) as dataCount,
        AVG(current) as avgCurrent,
        AVG(voltage) as avgVoltage,
        AVG(power) as avgPower,
        MAX(current) as maxCurrent,
        MAX(voltage) as maxVoltage,
        MAX(power) as maxPower,
        MIN(current) as minCurrent,
        MIN(voltage) as minVoltage,
        MIN(power) as minPower
      FROM device_data 
      WHERE deviceId = ? AND timestamp >= ? AND timestamp <= ?
    ''', [
      deviceId,
      startTime.millisecondsSinceEpoch,
      endTime.millisecondsSinceEpoch
    ]);

    return result.first;
  }

  /// 清理旧数据（保留指定天数的数据）
  Future<void> cleanOldData(int daysToKeep) async {
    final db = await database;
    final cutoffTime = DateTime.now().subtract(Duration(days: daysToKeep));

    await db.delete(
      'device_data',
      where: 'timestamp < ?',
      whereArgs: [cutoffTime.millisecondsSinceEpoch],
    );
  }

  /// 获取数据库大小信息
  Future<Map<String, int>> getDatabaseInfo() async {
    final db = await database;

    final deviceCount = Sqflite.firstIntValue(
            await db.rawQuery('SELECT COUNT(*) FROM devices')) ??
        0;

    final dataCount = Sqflite.firstIntValue(
            await db.rawQuery('SELECT COUNT(*) FROM device_data')) ??
        0;

    return {
      'deviceCount': deviceCount,
      'dataCount': dataCount,
    };
  }

  /// 保存设备设置
  Future<void> saveDeviceSettings(DeviceSettings settings) async {
    final db = await database;
    await db.insert(
      'device_settings',
      settings.toMap(),
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  /// 获取设备设置
  Future<DeviceSettings?> getDeviceSettings(String deviceId) async {
    final db = await database;
    final List<Map<String, dynamic>> maps = await db.query(
      'device_settings',
      where: 'deviceId = ?',
      whereArgs: [deviceId],
    );

    if (maps.isNotEmpty) {
      return DeviceSettings.fromMap(maps.first);
    }
    return null;
  }

  /// 获取所有设备设置
  Future<List<DeviceSettings>> getAllDeviceSettings() async {
    final db = await database;
    final List<Map<String, dynamic>> maps = await db.query('device_settings');

    return List.generate(maps.length, (i) {
      return DeviceSettings.fromMap(maps[i]);
    });
  }

  /// 删除设备设置
  Future<void> deleteDeviceSettings(String deviceId) async {
    final db = await database;
    await db.delete(
      'device_settings',
      where: 'deviceId = ?',
      whereArgs: [deviceId],
    );
  }

  /// 更新扫描间隔设置
  Future<void> updateScanInterval(int interval) async {
    final db = await database;
    await db.update(
      'scan_settings',
      {'scanInterval': interval},
      where: 'id = ?',
      whereArgs: [1],
    );
  }

  /// 获取扫描间隔设置
  Future<int> getScanInterval() async {
    final db = await database;
    final List<Map<String, dynamic>> maps = await db.query(
      'scan_settings',
      where: 'id = ?',
      whereArgs: [1],
    );

    if (maps.isNotEmpty) {
      return maps.first['scanInterval'] ?? 1000;
    }
    return 1000;
  }

  /// 计算设备的历史耗电量（基于数据库中的所有数据）
  Future<double> calculateDevicePowerConsumption(String deviceId,
      {DateTime? startTime, DateTime? endTime}) async {
    final db = await database;

    String sql = 'SELECT * FROM device_data WHERE deviceId = ?';
    List<dynamic> args = [deviceId];

    if (startTime != null) {
      sql += ' AND timestamp >= ?';
      args.add(startTime.millisecondsSinceEpoch);
    }

    if (endTime != null) {
      sql += ' AND timestamp <= ?';
      args.add(endTime.millisecondsSinceEpoch);
    }

    sql += ' ORDER BY timestamp ASC';

    final List<Map<String, dynamic>> maps = await db.rawQuery(sql, args);

    if (maps.length < 2) return 0.0;

    double totalConsumption = 0.0;

    for (int i = 1; i < maps.length; i++) {
      final current = DeviceData.fromMap(maps[i]);
      final previous = DeviceData.fromMap(maps[i - 1]);

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
  double _convertToMilliAmps(double current, String unit) {
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

  /// 获取设备每日耗电量统计
  Future<List<Map<String, dynamic>>> getDailyPowerConsumption(String deviceId,
      {int days = 30}) async {
    final db = await database;
    final endDate = DateTime.now();
    final startDate = endDate.subtract(Duration(days: days));

    List<Map<String, dynamic>> dailyStats = [];

    for (int i = 0; i < days; i++) {
      final date = startDate.add(Duration(days: i));
      final dayStart = DateTime(date.year, date.month, date.day);
      final dayEnd = DateTime(date.year, date.month, date.day, 23, 59, 59, 999);

      // 先检查该天是否有数据
      final dataCount = await db.rawQuery(
          'SELECT COUNT(*) as count FROM device_data WHERE deviceId = ? AND timestamp >= ? AND timestamp <= ?',
          [
            deviceId,
            dayStart.millisecondsSinceEpoch,
            dayEnd.millisecondsSinceEpoch
          ]);
      final count = Sqflite.firstIntValue(dataCount) ?? 0;

      double consumption = 0.0;
      if (count >= 2) {
        // 只有当数据点大于等于2时才计算耗电量
        consumption = await calculateDevicePowerConsumption(deviceId,
            startTime: dayStart, endTime: dayEnd);
      }

      dailyStats.add({
        'date': dayStart,
        'consumption': consumption,
        'dateString':
            '${date.month.toString().padLeft(2, '0')}-${date.day.toString().padLeft(2, '0')}',
      });
    }

    return dailyStats;
  }

  /// 获取设备月度耗电量统计
  Future<List<Map<String, dynamic>>> getMonthlyPowerConsumption(String deviceId,
      {int months = 12}) async {
    final db = await database;
    final endDate = DateTime.now();

    List<Map<String, dynamic>> monthlyStats = [];

    for (int i = 0; i < months; i++) {
      final date = DateTime(endDate.year, endDate.month - i, 1);
      final monthStart = DateTime(date.year, date.month, 1);
      final monthEnd = DateTime(date.year, date.month + 1, 0, 23, 59, 59, 999);

      // 先检查该月是否有数据
      final dataCount = await db.rawQuery(
          'SELECT COUNT(*) as count FROM device_data WHERE deviceId = ? AND timestamp >= ? AND timestamp <= ?',
          [
            deviceId,
            monthStart.millisecondsSinceEpoch,
            monthEnd.millisecondsSinceEpoch
          ]);
      final count = Sqflite.firstIntValue(dataCount) ?? 0;

      double consumption = 0.0;
      if (count >= 2) {
        // 只有当数据点大于等于2时才计算耗电量
        consumption = await calculateDevicePowerConsumption(deviceId,
            startTime: monthStart, endTime: monthEnd);
      }

      monthlyStats.add({
        'date': monthStart,
        'consumption': consumption,
        'dateString': '${date.month}月',
      });
    }

    return monthlyStats.reversed.toList();
  }

  /// 保存每日耗电量统计
  Future<void> saveDailyPowerConsumption(
      DailyPowerConsumption consumption) async {
    final db = await database;
    final now = DateTime.now().millisecondsSinceEpoch;

    await db.insert(
      'daily_power_consumption',
      {
        'deviceId': consumption.deviceId,
        'date': consumption.date.millisecondsSinceEpoch,
        'consumption': consumption.consumption,
        'dataPoints': consumption.dataPoints,
        'createdAt': now,
        'updatedAt': now,
      },
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  /// 获取设备的每日耗电量统计（返回DailyPowerConsumption对象）
  Future<List<DailyPowerConsumption>> getDailyPowerConsumptionObjects(
      String deviceId) async {
    final db = await database;

    final List<Map<String, dynamic>> maps = await db.query(
      'daily_power_consumption',
      where: 'deviceId = ?',
      whereArgs: [deviceId],
      orderBy: 'date DESC',
    );

    debugPrint('从数据库加载设备 $deviceId 的每日耗电量统计: ${maps.length} 条记录');

    if (maps.isNotEmpty) {
      for (var map in maps.take(3)) {
        // 只显示前3条
        debugPrint(
            '  - 日期: ${DateTime.fromMillisecondsSinceEpoch(map['date'])}, 耗电量: ${map['consumption']} mAh');
      }
    }

    return List.generate(maps.length, (i) {
      return DailyPowerConsumption.fromMap(maps[i]);
    });
  }

  /// 获取指定日期范围内的每日耗电量统计
  Future<List<DailyPowerConsumption>> getDailyPowerConsumptionInRange(
      String deviceId, DateTime startDate, DateTime endDate) async {
    final db = await database;

    final List<Map<String, dynamic>> maps = await db.query(
      'daily_power_consumption',
      where: 'deviceId = ? AND date >= ? AND date <= ?',
      whereArgs: [
        deviceId,
        startDate.millisecondsSinceEpoch,
        endDate.millisecondsSinceEpoch,
      ],
      orderBy: 'date ASC',
    );

    return List.generate(maps.length, (i) {
      return DailyPowerConsumption.fromMap(maps[i]);
    });
  }

  /// 删除指定日期之前的每日耗电量统计（用于清理旧数据）
  Future<void> deleteOldDailyPowerConsumption(int daysToKeep) async {
    final db = await database;
    final cutoffDate = DateTime.now().subtract(Duration(days: daysToKeep));

    await db.delete(
      'daily_power_consumption',
      where: 'date < ?',
      whereArgs: [cutoffDate.millisecondsSinceEpoch],
    );
  }

  /// 清空指定设备的所有每日耗电量统计
  Future<void> clearDailyPowerConsumption(String deviceId) async {
    final db = await database;

    await db.delete(
      'daily_power_consumption',
      where: 'deviceId = ?',
      whereArgs: [deviceId],
    );
  }

  /// 批量保存每日耗电量统计
  Future<void> saveDailyPowerConsumptionBatch(
      List<DailyPowerConsumption> consumptions) async {
    if (consumptions.isEmpty) return;

    final db = await database;
    final batch = db.batch();
    final now = DateTime.now().millisecondsSinceEpoch;

    debugPrint('准备保存 ${consumptions.length} 条每日耗电量统计数据到数据库');

    for (var consumption in consumptions) {
      batch.insert(
        'daily_power_consumption',
        {
          'deviceId': consumption.deviceId,
          'date': consumption.date.millisecondsSinceEpoch,
          'consumption': consumption.consumption,
          'dataPoints': consumption.dataPoints,
          'createdAt': now,
          'updatedAt': now,
        },
        conflictAlgorithm: ConflictAlgorithm.replace,
      );
    }

    final results = await batch.commit();
    debugPrint('成功保存每日耗电量统计数据，结果: $results');
  }

  /// 保存月度耗电量统计
  Future<void> saveMonthlyPowerConsumption(
      MonthlyPowerConsumption consumption) async {
    final db = await database;
    final now = DateTime.now().millisecondsSinceEpoch;

    await db.insert(
      'monthly_power_consumption',
      {
        'deviceId': consumption.deviceId,
        'year': consumption.year,
        'monthIndex': consumption.monthIndex,
        'consumption': consumption.consumption,
        'dataPoints': consumption.dataPoints,
        'createdAt': now,
        'updatedAt': now,
      },
      conflictAlgorithm: ConflictAlgorithm.replace,
    );

    debugPrint(
        '保存月度耗电量统计: ${consumption.deviceId} - ${consumption.monthKey} - ${consumption.consumption} mAh');
  }

  /// 获取设备的月度耗电量统计（返回MonthlyPowerConsumption对象列表）
  Future<List<MonthlyPowerConsumption>> getMonthlyPowerConsumptionObjects(
      String deviceId) async {
    final db = await database;

    final List<Map<String, dynamic>> maps = await db.query(
      'monthly_power_consumption',
      where: 'deviceId = ?',
      whereArgs: [deviceId],
      orderBy: 'year DESC, monthIndex DESC',
    );

    debugPrint('从数据库加载设备 $deviceId 的月度耗电量统计: ${maps.length} 条记录');

    return List.generate(maps.length, (i) {
      return MonthlyPowerConsumption.fromMap(maps[i]);
    });
  }

  /// 清空指定设备的所有月度耗电量统计
  Future<void> clearMonthlyPowerConsumption(String deviceId) async {
    final db = await database;

    await db.delete(
      'monthly_power_consumption',
      where: 'deviceId = ?',
      whereArgs: [deviceId],
    );

    debugPrint('清空设备 $deviceId 的月度耗电量统计数据');
  }

  /// 删除指定年份之前的月度耗电量统计（用于清理旧数据）
  Future<void> deleteOldMonthlyPowerConsumption(int yearsToKeep) async {
    final db = await database;
    final cutoffYear = DateTime.now().year - yearsToKeep;

    await db.delete(
      'monthly_power_consumption',
      where: 'year < ?',
      whereArgs: [cutoffYear],
    );

    debugPrint('删除 $cutoffYear 年之前的月度耗电量统计数据');
  }

  /// 保存每日耗电量统计数组到数据库
  Future<void> saveDailyConsumptionArray(
      String deviceId, List<double?> dailyArray) async {
    final db = await database;
    final batch = db.batch();
    final now = DateTime.now().millisecondsSinceEpoch;

    // 获取基准日期（2020年1月1日）
    final baseDate = DateTime(2020, 1, 1);

    for (int i = 0; i < dailyArray.length; i++) {
      if (dailyArray[i] != null && dailyArray[i]! > 0) {
        final targetDate = baseDate.add(Duration(days: i));
        final dateTimestamp =
            DateTime(targetDate.year, targetDate.month, targetDate.day)
                .millisecondsSinceEpoch;

        batch.insert(
          'daily_power_consumption',
          {
            'deviceId': deviceId,
            'date': dateTimestamp,
            'consumption': dailyArray[i]!,
            'dataPoints': 1, // 简化处理，实际应该统计数据点数量
            'createdAt': now,
            'updatedAt': now,
          },
          conflictAlgorithm: ConflictAlgorithm.replace,
        );
      }
    }

    await batch.commit();
    debugPrint('保存设备 $deviceId 的每日耗电量统计数组到数据库');
  }

  /// 保存月度耗电量统计数组到数据库
  Future<void> saveMonthlyConsumptionArray(
      String deviceId, List<double?> monthlyArray) async {
    final db = await database;
    final batch = db.batch();
    final now = DateTime.now().millisecondsSinceEpoch;

    // 获取当前年份
    final currentYear = DateTime.now().year;

    for (int i = 0; i < monthlyArray.length; i++) {
      if (monthlyArray[i] != null && monthlyArray[i]! > 0) {
        batch.insert(
          'monthly_power_consumption',
          {
            'deviceId': deviceId,
            'year': currentYear,
            'monthIndex': i,
            'consumption': monthlyArray[i]!,
            'dataPoints': 1, // 简化处理，实际应该统计数据点数量
            'createdAt': now,
            'updatedAt': now,
          },
          conflictAlgorithm: ConflictAlgorithm.replace,
        );
      }
    }

    await batch.commit();
    debugPrint('保存设备 $deviceId 的月度耗电量统计数组到数据库');
  }

  /// 保存骑行记录
  Future<int> insertRide(RideSession ride) async {
    final db = await database;
    await _createRideTables(db);
    final values = ride.toMap()
      ..remove('id')
      ..['createdAt'] = DateTime.now().millisecondsSinceEpoch;
    return await db.insert('rides', values);
  }

  Future<void> insertRidePoints(int rideId, List<RidePoint> points) async {
    if (points.isEmpty) return;

    final db = await database;
    await _createRideTables(db);
    final batch = db.batch();
    for (final point in points) {
      batch.insert('ride_points', point.toMap(savedRideId: rideId));
    }
    await batch.commit(noResult: true);
  }

  Future<List<RideSession>> getRides({int? limit}) async {
    final db = await database;
    await _createRideTables(db);
    final maps = await db.query(
      'rides',
      orderBy: 'startTime DESC',
      limit: limit,
    );
    return maps.map(RideSession.fromMap).toList();
  }

  Future<List<RideSession>> getRecentRides({int limit = 20}) {
    return getRides(limit: limit);
  }

  Future<List<RidePoint>> getRidePoints(int rideId) async {
    final db = await database;
    await _createRideTables(db);
    final maps = await db.query(
      'ride_points',
      where: 'rideId = ?',
      whereArgs: [rideId],
      orderBy: 'timestamp ASC',
    );
    return maps.map(RidePoint.fromMap).toList();
  }

  Future<Map<String, double>> getRideTotals({DateTime? since}) async {
    final db = await database;
    await _createRideTables(db);
    final rows = await db.rawQuery(
      '''
      SELECT
        COALESCE(SUM(distanceKm), 0) AS distanceKm,
        COALESCE(SUM(durationSeconds), 0) AS durationSeconds,
        COALESCE(MAX(maxSpeedKmh), 0) AS maxSpeedKmh,
        COALESCE(SUM(totalClimbM), 0) AS totalClimbM
      FROM rides
      ${since == null ? '' : 'WHERE startTime >= ?'}
      ''',
      since == null ? const [] : [since.millisecondsSinceEpoch],
    );
    final row = rows.first;
    return {
      'distanceKm': (row['distanceKm'] as num).toDouble(),
      'durationSeconds': (row['durationSeconds'] as num).toDouble(),
      'maxSpeedKmh': (row['maxSpeedKmh'] as num).toDouble(),
      'totalClimbM': (row['totalClimbM'] as num).toDouble(),
    };
  }

  Future<void> deleteRide(int rideId) async {
    final db = await database;
    await _createRideTables(db);
    await db.transaction((txn) async {
      await txn.delete(
        'ride_points',
        where: 'rideId = ?',
        whereArgs: [rideId],
      );
      await txn.delete(
        'rides',
        where: 'id = ?',
        whereArgs: [rideId],
      );
    });
  }

  /// 关闭数据库
  Future<void> close() async {
    if (_database != null) {
      await _database!.close();
      _database = null;
    }
  }

  // ================= 自定义按钮（全局共享）=================

  Future<void> upsertCustomButton({
    required String id,
    required String name,
    required int iconCode,
    required int colorValue,
    required bool isHex,
    required String payload,
  }) async {
    final db = await database;
    await _ensureCustomButtonsTable(db);
    final now = DateTime.now().millisecondsSinceEpoch;
    await db.insert(
      'custom_buttons',
      {
        'id': id,
        'name': name,
        'iconCode': iconCode,
        'colorValue': colorValue,
        'isHex': isHex ? 1 : 0,
        'payload': payload,
        'createdAt': now,
        'updatedAt': now,
      },
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  Future<List<Map<String, dynamic>>> getCustomButtons() async {
    final db = await database;
    await _ensureCustomButtonsTable(db);
    return await db.query('custom_buttons', orderBy: 'updatedAt DESC');
  }

  Future<void> deleteCustomButton(String id) async {
    final db = await database;
    await _ensureCustomButtonsTable(db);
    await db.delete('custom_buttons', where: 'id = ?', whereArgs: [id]);
  }

  Future<void> _ensureCustomButtonsTable(Database db) async {
    try {
      await db.execute('''
        CREATE TABLE IF NOT EXISTS custom_buttons (
          id TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          iconCode INTEGER NOT NULL,
          colorValue INTEGER NOT NULL,
          isHex INTEGER NOT NULL,
          payload TEXT NOT NULL,
          createdAt INTEGER,
          updatedAt INTEGER
        )
      ''');
    } catch (e) {
      debugPrint('确保自定义按钮表存在失败: $e');
    }
  }
}
