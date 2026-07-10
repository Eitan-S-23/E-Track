import 'dart:convert';

import 'package:dio/dio.dart';

import '../config/share_links.dart';

class AnnouncementService {
  AnnouncementService._();

  static final Dio _dio = Dio(
    BaseOptions(
      connectTimeout: const Duration(seconds: 8),
      receiveTimeout: const Duration(seconds: 12),
    ),
  );

  static Future<List<TraceAnnouncement>> fetchAnnouncements() async {
    if (!ShareLinks.hasAnnouncementsEndpoint) {
      return fallbackAnnouncements;
    }

    try {
      final response = await _dio.getUri(ShareLinks.announcementsUri());
      final data = response.data is String
          ? jsonDecode(response.data as String)
          : response.data;
      if (data is! Map) return fallbackAnnouncements;

      final rawItems = data['announcements'];
      if (rawItems is! List) return fallbackAnnouncements;

      final items = rawItems
          .whereType<Map>()
          .map(TraceAnnouncement.fromJson)
          .where((item) => item.title.isNotEmpty && item.body.isNotEmpty)
          .toList(growable: false);
      return items.isEmpty ? fallbackAnnouncements : items;
    } catch (_) {
      return fallbackAnnouncements;
    }
  }

  static const fallbackAnnouncements = [
    TraceAnnouncement(
      id: 'local-release',
      type: TraceAnnouncementType.release,
      title: '更新公告',
      body: '检查更新入口位于“我的”页面。\n'
          '更新服务负责应用版本维护与增量升级。\n'
          '新版本发布后，检查更新时会自动提示。',
    ),
    TraceAnnouncement(
      id: 'local-manual',
      type: TraceAnnouncementType.manual,
      title: '公告通知',
      body: '这里会显示后台发布的手动公告。\n'
          '连接 Cloudflare 更新服务后，公告内容会自动刷新。',
    ),
  ];
}

enum TraceAnnouncementType {
  manual,
  release;

  String get label {
    switch (this) {
      case TraceAnnouncementType.manual:
        return '公告通知';
      case TraceAnnouncementType.release:
        return '更新公告';
    }
  }
}

class TraceAnnouncement {
  const TraceAnnouncement({
    required this.id,
    required this.type,
    required this.title,
    required this.body,
    this.releaseTag,
    this.versionName,
    this.versionCode,
  });

  factory TraceAnnouncement.fromJson(Map<dynamic, dynamic> json) {
    final type = json['type'] == 'release'
        ? TraceAnnouncementType.release
        : TraceAnnouncementType.manual;
    return TraceAnnouncement(
      id: (json['id'] ?? '').toString(),
      type: type,
      title: (json['title'] ?? '').toString(),
      body: (json['body'] ?? '').toString(),
      releaseTag: _optionalString(json['releaseTag']),
      versionName: _optionalString(json['versionName']),
      versionCode: _optionalInt(json['versionCode']),
    );
  }

  final String id;
  final TraceAnnouncementType type;
  final String title;
  final String body;
  final String? releaseTag;
  final String? versionName;
  final int? versionCode;

  static String? _optionalString(Object? value) {
    final text = value?.toString().trim() ?? '';
    return text.isEmpty ? null : text;
  }

  static int? _optionalInt(Object? value) {
    if (value is int) return value;
    return int.tryParse(value?.toString() ?? '');
  }
}
