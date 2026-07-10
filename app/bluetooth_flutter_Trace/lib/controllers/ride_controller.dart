import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';
import 'package:get/get.dart';

import '../models/ride_models.dart';
import '../services/database_service.dart';

class RideController extends GetxController {
  static RideController get to => Get.find<RideController>();

  final DatabaseService _db = DatabaseService();

  final isRecording = false.obs;
  final isPaused = false.obs;
  final currentSpeedKmh = 0.0.obs;
  final avgSpeedKmh = 0.0.obs;
  final maxSpeedKmh = 0.0.obs;
  final distanceKm = 0.0.obs;
  final elapsed = Duration.zero.obs;
  final altitudeM = 0.0.obs;
  final totalClimbM = 0.0.obs;
  final gpsAccuracyM = 0.0.obs;
  final gpsStatus = 'GPS 未定位'.obs;
  final currentPaceSecondsPerKm = 0.0.obs;
  final caloriesKcal = 0.obs;
  final recentRides = <RideSession>[].obs;
  final rideHistory = <RideSession>[].obs;
  final weeklyDistancesKm = <double>[].obs;
  final monthlyDistanceKm = 0.0.obs;
  final monthGoalKm = 500.0.obs;
  final speedTrendKmh = <double>[].obs;
  final altitudeTrendM = <double>[].obs;
  final activeTabIndex = 0.obs;
  final selectedRoute = Rxn<RideRouteSelection>();

  StreamSubscription<Position>? _positionSub;
  Timer? _timer;
  DateTime? _startTime;
  Position? _lastPosition;
  DateTime? _lastPositionTime;
  double? _lastAltitudeM;
  int _activeSeconds = 0;
  double _speedSum = 0.0;
  int _speedSamples = 0;
  final _points = <RidePoint>[].obs;

  List<RidePoint> get points => List.unmodifiable(_points);

  void selectTab(int index) {
    if (index < 0 || index > 3) return;
    activeTabIndex.value = index;
  }

  void selectRoute(RideRouteSelection route) {
    selectedRoute.value = route;
  }

  void clearSelectedRoute([String? title]) {
    final current = selectedRoute.value;
    if (title == null || current?.title == title) {
      selectedRoute.value = null;
    }
  }

  @override
  void onInit() {
    super.onInit();
    loadRideHistory();
    unawaited(refreshGpsStatus());
  }

  Future<void> loadRideHistory() async {
    try {
      final rides = await _db.getRides();
      rideHistory.assignAll(rides);
      recentRides.assignAll(rides.take(20).toList());
      weeklyDistancesKm.assignAll(_buildWeeklyDistances(rideHistory));
      final now = DateTime.now();
      final monthStart = DateTime(now.year, now.month);
      final totals = await _db.getRideTotals(since: monthStart);
      monthlyDistanceKm.value = totals['distanceKm'] ?? 0.0;
    } catch (e) {
      debugPrint('Load ride history failed: $e');
    }
  }

  Future<void> refreshGpsStatus({bool requestPermission = false}) async {
    final serviceEnabled = await Geolocator.isLocationServiceEnabled();
    if (!serviceEnabled) {
      gpsStatus.value = '定位服务关闭';
      return;
    }

    var permission = await Geolocator.checkPermission();
    if (requestPermission && permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
    }

    if (permission == LocationPermission.denied) {
      gpsStatus.value = 'GPS 未授权';
      return;
    }
    if (permission == LocationPermission.deniedForever) {
      gpsStatus.value = 'GPS 权限被禁用';
      return;
    }

    gpsStatus.value = 'GPS 就绪';
  }

  Future<bool> _ensurePermission() async {
    final serviceEnabled = await Geolocator.isLocationServiceEnabled();
    if (!serviceEnabled) {
      gpsStatus.value = '定位服务关闭';
      Get.snackbar('定位不可用', '请先开启系统定位服务', snackPosition: SnackPosition.BOTTOM);
      await Geolocator.openLocationSettings();
      return false;
    }

    var permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
    }

    if (permission == LocationPermission.deniedForever) {
      gpsStatus.value = 'GPS 权限被禁用';
      Get.snackbar('定位权限被禁用', '请在系统设置中允许定位权限',
          snackPosition: SnackPosition.BOTTOM);
      await Geolocator.openAppSettings();
      return false;
    }

    final allowed = permission == LocationPermission.whileInUse ||
        permission == LocationPermission.always;
    if (!allowed) {
      gpsStatus.value = 'GPS 未授权';
      Get.snackbar('定位权限未授予', '无法开始记录骑行',
          snackPosition: SnackPosition.BOTTOM);
    }
    return allowed;
  }

  Future<void> start() async {
    if (isRecording.value) return;
    if (!await _ensurePermission()) return;

    _resetRideState();
    isRecording.value = true;
    isPaused.value = false;
    _startTime = DateTime.now();
    gpsStatus.value = 'GPS 搜星中';

    _timer?.cancel();
    _timer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (!isRecording.value || isPaused.value) return;
      _activeSeconds += 1;
      elapsed.value = Duration(seconds: _activeSeconds);
      _updateDerivedMetrics();
    });

    _positionSub?.cancel();
    _positionSub = Geolocator.getPositionStream(
      locationSettings: _rideLocationSettings(),
    ).listen(
      _onPosition,
      onError: (Object error) {
        gpsStatus.value = 'GPS 异常';
        Get.snackbar('GPS 异常', '无法读取定位数据，计时仍在继续',
            snackPosition: SnackPosition.BOTTOM);
        debugPrint('Position stream error: $error');
      },
    );

    Get.snackbar('开始记录', '正在记录骑行，静止时速度和距离会保持 0',
        snackPosition: SnackPosition.BOTTOM);
    unawaited(_seedCurrentPosition());
  }

  void pauseResume() {
    if (!isRecording.value) return;
    isPaused.value = !isPaused.value;
    gpsStatus.value = isPaused.value ? '已暂停' : 'GPS 记录中';
  }

  Future<void> saveCurrentRide() async {
    if (!isRecording.value) {
      await loadRideHistory();
      Get.snackbar('暂无可保存骑行', '请先点击开始记录，再点击保存',
          snackPosition: SnackPosition.BOTTOM);
      return;
    }

    final ride = await stopAndSave();
    if (ride != null &&
        ride.durationSeconds == 0 &&
        ride.distanceKm == 0 &&
        _points.isEmpty) {
      Get.snackbar('未保存', '本次没有有效时长或 GPS 轨迹',
          snackPosition: SnackPosition.BOTTOM);
    }
  }

  Future<RideSession?> stopAndSave({
    String deviceId = '',
    String deviceName = '',
  }) async {
    if (!isRecording.value) return null;

    isRecording.value = false;
    isPaused.value = false;
    await _positionSub?.cancel();
    _positionSub = null;
    _timer?.cancel();
    _timer = null;

    final end = DateTime.now();
    final start = _startTime ?? end;
    final ride = RideSession(
      deviceId: deviceId,
      deviceName: deviceName,
      startTime: start,
      endTime: end,
      durationSeconds: _activeSeconds,
      distanceKm: _round(distanceKm.value, 3),
      avgSpeedKmh: _round(avgSpeedKmh.value, 2),
      maxSpeedKmh: _round(maxSpeedKmh.value, 2),
      totalClimbM: _round(totalClimbM.value, 1),
    );

    if (ride.durationSeconds > 0 || ride.distanceKm > 0 || _points.isNotEmpty) {
      final rideId = await _db.insertRide(ride);
      await _db.insertRidePoints(rideId, List<RidePoint>.of(_points));
      await loadRideHistory();
      Get.snackbar('骑行已保存', '记录 ${ride.distanceKm.toStringAsFixed(2)} km',
          snackPosition: SnackPosition.BOTTOM);
    }

    gpsStatus.value = 'GPS 未定位';
    return ride;
  }

  void _resetRideState() {
    currentSpeedKmh.value = 0;
    avgSpeedKmh.value = 0;
    maxSpeedKmh.value = 0;
    distanceKm.value = 0;
    elapsed.value = Duration.zero;
    altitudeM.value = 0;
    totalClimbM.value = 0;
    gpsAccuracyM.value = 0;
    currentPaceSecondsPerKm.value = 0;
    caloriesKcal.value = 0;
    speedTrendKmh.clear();
    altitudeTrendM.clear();
    _activeSeconds = 0;
    _speedSum = 0;
    _speedSamples = 0;
    _lastPosition = null;
    _lastPositionTime = null;
    _lastAltitudeM = null;
    _points.clear();
  }

  Future<void> _seedCurrentPosition() async {
    try {
      final position = await Geolocator.getCurrentPosition(
        locationSettings: _rideLocationSettings(),
      ).timeout(const Duration(seconds: 8));
      _onPosition(position);
    } on TimeoutException {
      gpsStatus.value = '等待 GPS 数据';
    } catch (e) {
      gpsStatus.value = '等待 GPS 数据';
      debugPrint('Initial position failed: $e');
    }
  }

  void _onPosition(Position position) {
    if (!isRecording.value || isPaused.value) return;

    final now = DateTime.now();
    final speedKmh = _normalizedSpeedKmh(position, now);
    currentSpeedKmh.value = _round(speedKmh, 2);
    _pushTrend(speedTrendKmh, currentSpeedKmh.value);
    _speedSum += speedKmh;
    _speedSamples += 1;
    avgSpeedKmh.value =
        _round(_speedSamples == 0 ? 0 : _speedSum / _speedSamples, 2);
    if (speedKmh > maxSpeedKmh.value) {
      maxSpeedKmh.value = _round(speedKmh, 2);
    }

    final currentAltitude =
        position.altitude.isFinite ? position.altitude : 0.0;
    altitudeM.value = _round(currentAltitude, 1);
    _pushTrend(altitudeTrendM, altitudeM.value);
    gpsAccuracyM.value =
        _round(position.accuracy.isFinite ? position.accuracy : 0.0, 1);
    gpsStatus.value = gpsAccuracyM.value <= 15 ? 'GPS 良好' : 'GPS 较弱';

    if (_lastPosition != null) {
      final meters = Geolocator.distanceBetween(
        _lastPosition!.latitude,
        _lastPosition!.longitude,
        position.latitude,
        position.longitude,
      );
      if (meters.isFinite && meters >= 0.5 && meters <= 1000) {
        distanceKm.value = _round(distanceKm.value + meters / 1000, 3);
      }
    }

    if (_lastAltitudeM != null) {
      final climb = currentAltitude - _lastAltitudeM!;
      if (climb > 0.5 && climb < 50) {
        totalClimbM.value = _round(totalClimbM.value + climb, 1);
      }
    }

    _lastPosition = position;
    _lastPositionTime = now;
    _lastAltitudeM = currentAltitude;
    _points.add(
      RidePoint(
        rideId: -1,
        timestamp: now,
        latitude: position.latitude,
        longitude: position.longitude,
        speedKmh: currentSpeedKmh.value,
        altitudeM: altitudeM.value,
      ),
    );

    _updateDerivedMetrics();
  }

  double _normalizedSpeedKmh(Position position, DateTime now) {
    if (position.speed.isFinite && position.speed > 0.2) {
      return position.speed * 3.6;
    }
    if (_lastPosition == null || _lastPositionTime == null) return 0;

    final seconds = now.difference(_lastPositionTime!).inMilliseconds /
        1000;
    if (seconds <= 0) return 0;

    final meters = Geolocator.distanceBetween(
      _lastPosition!.latitude,
      _lastPosition!.longitude,
      position.latitude,
      position.longitude,
    );
    return meters / seconds * 3.6;
  }

  LocationSettings _rideLocationSettings() {
    if (defaultTargetPlatform == TargetPlatform.android) {
      return AndroidSettings(
        accuracy: LocationAccuracy.bestForNavigation,
        distanceFilter: 1,
        intervalDuration: const Duration(seconds: 1),
      );
    }
    if (defaultTargetPlatform == TargetPlatform.iOS ||
        defaultTargetPlatform == TargetPlatform.macOS) {
      return AppleSettings(
        accuracy: LocationAccuracy.bestForNavigation,
        distanceFilter: 1,
        activityType: ActivityType.fitness,
        pauseLocationUpdatesAutomatically: false,
      );
    }
    return const LocationSettings(
      accuracy: LocationAccuracy.bestForNavigation,
      distanceFilter: 1,
    );
  }

  void _updateDerivedMetrics() {
    if (distanceKm.value > 0) {
      currentPaceSecondsPerKm.value = _activeSeconds / distanceKm.value;
      caloriesKcal.value = (distanceKm.value * 24).round();
    } else {
      currentPaceSecondsPerKm.value = 0;
      caloriesKcal.value = 0;
    }
  }

  void _pushTrend(RxList<double> target, double value) {
    target.add(value);
    if (target.length > 80) {
      target.removeAt(0);
    }
  }

  List<double> _buildWeeklyDistances(List<RideSession> rides) {
    final now = DateTime.now();
    final start = DateTime(now.year, now.month, now.day)
        .subtract(const Duration(days: 6));
    final values = List<double>.filled(7, 0);

    for (final ride in rides) {
      final day = DateTime(
        ride.startTime.year,
        ride.startTime.month,
        ride.startTime.day,
      );
      final index = day.difference(start).inDays;
      if (index >= 0 && index < values.length) {
        values[index] += ride.distanceKm;
      }
    }

    return values.map((value) => _round(value, 2)).toList();
  }

  double _round(double value, int digits) {
    final text = value.toStringAsFixed(digits);
    return double.parse(text);
  }

  @override
  void onClose() {
    _positionSub?.cancel();
    _timer?.cancel();
    super.onClose();
  }
}
