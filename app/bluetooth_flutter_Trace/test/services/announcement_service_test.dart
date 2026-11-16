import 'package:flutter/foundation.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:ble_monitor/config/share_links.dart';
import 'package:ble_monitor/services/announcement_service.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUp(() { SharedPreferences.setMockInitialValues({}); });
  tearDown(() { debugDefaultTargetPlatformOverride = null; });

  TraceAnnouncement notice(String id, {int time = 1700000000, bool pin = false}) =>
      TraceAnnouncement.fromJson({'id': id, 'title': id, 'body': 'body',
        'pinned': pin, 'publishedAt': time, 'type': 'manual'});

  test('publication time uses server seconds and pin only controls order', () {
    final items = [notice('new', time: 1700000002), notice('old', pin: true),
      notice('middle', time: 1700000001)]..sort(TraceAnnouncement.compare);
    expect(items.map((x) => x.id), ['old', 'new', 'middle']);
    expect(items.first.publishedAt!.millisecondsSinceEpoch, 1700000000000);
    expect(items.first.publishedAt!.isUtc, isTrue);
    expect(TraceAnnouncement.fromJson({'publishedAt': 'bad'}).publishedAt, isNull);
  });

  test('fetching or deferring does not mark a notice as presented', () async {
    final items = [notice('one'), notice('two')];
    expect(await AnnouncementService.unseen(items), hasLength(2));
    await AnnouncementService.markPresented(items.first);
    expect((await AnnouncementService.unseen(items)).single.id, 'two');
    expect(await AnnouncementService.unseen([notice('one', pin: true)]), isEmpty);
    expect(await AnnouncementService.unseen([notice('one', time: 1700000001)]), hasLength(1));
  });

  test('release and offline fallback entries never become automatic notices', () async {
    final release = TraceAnnouncement.fromJson({'id': 'release', 'type': 'release'});
    expect(await AnnouncementService.unseen([
      ...AnnouncementService.fallbackAnnouncements, release,
    ]), isEmpty);
  });

  test('platform and seen state are not hardcoded to Android', () async {
    debugDefaultTargetPlatformOverride = TargetPlatform.android;
    final item = notice('one');
    await AnnouncementService.markPresented(item);
    debugDefaultTargetPlatformOverride = TargetPlatform.iOS;
    expect(ShareLinks.clientPlatform, 'ios');
    expect(await AnnouncementService.unseen([item]), hasLength(1));
    debugDefaultTargetPlatformOverride = TargetPlatform.windows;
    expect(ShareLinks.clientPlatform, 'windows');
  });
}
