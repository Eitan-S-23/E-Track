class RideSession {
  final int? id;
  final String deviceId;
  final String deviceName;
  final DateTime startTime;
  final DateTime endTime;
  final int durationSeconds;
  final double distanceKm;
  final double avgSpeedKmh;
  final double maxSpeedKmh;
  final double totalClimbM;

  RideSession({
    this.id,
    required this.deviceId,
    required this.deviceName,
    required this.startTime,
    required this.endTime,
    required this.durationSeconds,
    required this.distanceKm,
    required this.avgSpeedKmh,
    required this.maxSpeedKmh,
    required this.totalClimbM,
  });

  Map<String, dynamic> toMap() {
    return {
      if (id != null) 'id': id,
      'deviceId': deviceId,
      'deviceName': deviceName,
      'startTime': startTime.millisecondsSinceEpoch,
      'endTime': endTime.millisecondsSinceEpoch,
      'durationSeconds': durationSeconds,
      'distanceKm': distanceKm,
      'avgSpeedKmh': avgSpeedKmh,
      'maxSpeedKmh': maxSpeedKmh,
      'totalClimbM': totalClimbM,
    };
  }

  factory RideSession.fromMap(Map<String, dynamic> map) {
    return RideSession(
      id: map['id'] as int?,
      deviceId: (map['deviceId'] ?? '') as String,
      deviceName: (map['deviceName'] ?? '') as String,
      startTime: DateTime.fromMillisecondsSinceEpoch(map['startTime'] as int),
      endTime: DateTime.fromMillisecondsSinceEpoch(map['endTime'] as int),
      durationSeconds: map['durationSeconds'] as int,
      distanceKm: (map['distanceKm'] as num).toDouble(),
      avgSpeedKmh: (map['avgSpeedKmh'] as num).toDouble(),
      maxSpeedKmh: (map['maxSpeedKmh'] as num).toDouble(),
      totalClimbM: (map['totalClimbM'] as num).toDouble(),
    );
  }
}

class RidePoint {
  final int? id;
  final int rideId;
  final DateTime timestamp;
  final double latitude;
  final double longitude;
  final double speedKmh;
  final double altitudeM;

  RidePoint({
    this.id,
    required this.rideId,
    required this.timestamp,
    required this.latitude,
    required this.longitude,
    required this.speedKmh,
    required this.altitudeM,
  });

  Map<String, dynamic> toMap({int? savedRideId}) {
    return {
      if (id != null) 'id': id,
      'rideId': savedRideId ?? rideId,
      'timestamp': timestamp.millisecondsSinceEpoch,
      'latitude': latitude,
      'longitude': longitude,
      'speedKmh': speedKmh,
      'altitudeM': altitudeM,
    };
  }

  factory RidePoint.fromMap(Map<String, dynamic> map) {
    return RidePoint(
      id: map['id'] as int?,
      rideId: map['rideId'] as int,
      timestamp: DateTime.fromMillisecondsSinceEpoch(map['timestamp'] as int),
      latitude: (map['latitude'] as num).toDouble(),
      longitude: (map['longitude'] as num).toDouble(),
      speedKmh: (map['speedKmh'] as num).toDouble(),
      altitudeM: (map['altitudeM'] as num).toDouble(),
    );
  }
}

class RideRoutePoint {
  const RideRoutePoint({
    required this.latitude,
    required this.longitude,
    this.altitudeM,
  });

  final double latitude;
  final double longitude;
  final double? altitudeM;
}

class RideRouteSelection {
  const RideRouteSelection({
    required this.title,
    required this.date,
    required this.distance,
    required this.climb,
    required this.duration,
    required this.difficulty,
    required this.difficultyColorValue,
    required this.variant,
    this.track = const <RideRoutePoint>[],
  });

  final String title;
  final String date;
  final String distance;
  final String climb;
  final String duration;
  final String difficulty;
  final int difficultyColorValue;
  final int variant;
  final List<RideRoutePoint> track;
}
