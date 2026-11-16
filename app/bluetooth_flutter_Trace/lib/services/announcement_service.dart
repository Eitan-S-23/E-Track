import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:shared_preferences/shared_preferences.dart';

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
    final items = await fetchRemoteAnnouncements();
    return items.isEmpty ? fallbackAnnouncements : items;
  }

  static Future<List<TraceAnnouncement>> fetchRemoteAnnouncements() async {
    if (!ShareLinks.hasAnnouncementsEndpoint) {
      return const [];
    }

    try {
      final response = await _dio.getUri(ShareLinks.announcementsUri());
      final data = response.data is String
          ? jsonDecode(response.data as String)
          : response.data;
      if (data is! Map) return const [];

      final rawItems = data['announcements'];
      if (rawItems is! List) return const [];

      final items = rawItems
          .whereType<Map>()
          .map(TraceAnnouncement.fromJson)
          .where((item) => item.id.isNotEmpty && item.title.isNotEmpty && item.body.isNotEmpty)
          .toList();
      items.sort(TraceAnnouncement.compare);
      return items;
    } catch (_) {
      return const [];
    }
  }

  static String get _seenKey => 'announcements.seen.v1.${ShareLinks.appId}.'
      '${ShareLinks.clientPlatform}.${ShareLinks.updateChannel}';
  static final _presented = <String, Set<String>>{};

  static bool wasPresented(TraceAnnouncement item) =>
      _presented[_seenKey]?.contains(item.publicationIdentity) ?? false;

  static Future<List<TraceAnnouncement>> unseen(List<TraceAnnouncement> items) async {
    final prefs = await SharedPreferences.getInstance();
    final seen = (prefs.getStringList(_seenKey) ?? const <String>[]).toSet();
    _presented[_seenKey] = seen;
    return items.where((item) => item.type == TraceAnnouncementType.manual &&
        !item.id.startsWith('local-') && !seen.contains(item.publicationIdentity)).toList();
  }

  static Future<void> markPresented(TraceAnnouncement item) async {
    if (item.type != TraceAnnouncementType.manual || item.id.startsWith('local-')) return;
    final prefs = await SharedPreferences.getInstance();
    final seen = (prefs.getStringList(_seenKey) ?? const <String>[]).toSet()
      ..add(item.publicationIdentity);
    _presented[_seenKey] = seen;
    await prefs.setStringList(_seenKey, seen.toList());
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
    this.pinned = false,
    this.publishedAt,
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
      pinned: json['pinned'] == true || json['pinned'] == 1,
      publishedAt: _publicationTime(json['publishedAt']),
    );
  }

  final String id;
  final TraceAnnouncementType type;
  final String title;
  final String body;
  final String? releaseTag;
  final String? versionName;
  final int? versionCode;
  final bool pinned;
  final DateTime? publishedAt;

  String get publicationIdentity => '$id@${publishedAt?.millisecondsSinceEpoch ?? 0}';

  static int compare(TraceAnnouncement a, TraceAnnouncement b) {
    if (a.pinned != b.pinned) return a.pinned ? -1 : 1;
    final time = (b.publishedAt?.millisecondsSinceEpoch ?? 0)
        .compareTo(a.publishedAt?.millisecondsSinceEpoch ?? 0);
    return time != 0 ? time : a.id.compareTo(b.id);
  }

  static DateTime? _publicationTime(Object? value) {
    final seconds = _optionalInt(value);
    if (seconds != null && seconds > 0 && seconds < 8640000000000) {
      return DateTime.fromMillisecondsSinceEpoch(seconds * 1000, isUtc: true);
    }
    if (value is! String) return null;
    final text = value.trim();
    // D1 datetime('now') is UTC but its SQLite text has no zone suffix.
    final sqlUtc = RegExp(r'^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?$').hasMatch(text);
    return DateTime.tryParse(sqlUtc ? '${text}Z' : text)?.toUtc();
  }

  static String? _optionalString(Object? value) {
    final text = value?.toString().trim() ?? '';
    return text.isEmpty ? null : text;
  }

  static int? _optionalInt(Object? value) {
    if (value is int) return value;
    return int.tryParse(value?.toString() ?? '');
  }
}
