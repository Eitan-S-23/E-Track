import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math' as math;
import 'dart:typed_data';

import 'package:crypto/crypto.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:ble_monitor/ota/ota_download.dart';
import 'package:ble_monitor/ota/ota_firmware_latest.dart';

/// download owner：sidecar 身份、Range 续传、校验失败 fail closed。
/// RC3-10/11：看码分流（空/未知 errorCode 不按状态猜测刷新）、
/// Dio badResponse 统一转换、强 ETag 两处校验（sidecar + 响应）、
/// Content-Digest 唯一项/规范编码、早退路径有界 drain（字节级观测）。
///
/// 用 Dio 的 HttpMockAdapter 不可用时退而求其次：直接子类化 Dio 并
/// 注入自定义 HttpClientAdapter 模拟 200/206/416 响应。
void main() {
  late Directory tempDir;

  setUp(() {
    tempDir = Directory.systemTemp.createTempSync('ota_download_test');
  });

  tearDown(() {
    if (tempDir.existsSync()) {
      tempDir.deleteSync(recursive: true);
    }
  });

  Uint8List assetBytes(int size) =>
      Uint8List.fromList(List<int>.generate(size, (i) => (i * 7 + 3) & 0xFF));

  OtaFirmwareAsset assetOf(Uint8List bytes, {String assetId = 'asset-1'}) {
    return OtaFirmwareAsset(
      assetId: assetId,
      kind: 'full',
      fileName: 'pkg.etu',
      sha256: sha256.convert(bytes).toString(),
      sizeBytes: bytes.length,
      baseVersionCode: 0,
      baseImageSha256: null,
      downloadUrl: 'http://localhost:9/pkg.etu',
      expiresAt: 1780000000,
    );
  }

  /// 构造走自定义 adapter 的 Dio：按请求 Range 决定 200/206，
  /// 可注入 PR13 头违规/分类码/digest 行为。
  Dio dioWithServer(
    Uint8List bytes, {
    String etag = '"strong-etag"',
    List<void Function(RequestOptions)>? requestLog,
    _MockBehavior behavior = const _MockBehavior(),
  }) {
    final dio = Dio();
    dio.httpClientAdapter =
        _MockAdapter(bytes, etag, requestLog ?? [], behavior);
    return dio;
  }

  OtaFirmwareDownload downloader(Dio dio) => OtaFirmwareDownload(
        dio: dio,
        dirProvider: () async => tempDir,
      );

  group('完整下载', () {
    test('200 全量下载 + 长度/SHA 校验 + 原子 rename', () async {
      final bytes = assetBytes(1024);
      final dio = dioWithServer(bytes);
      final file = await downloader(dio).download(
        asset: assetOf(bytes),
        releaseId: 'rel-1',
        downloadUrl: 'http://localhost:9/pkg.etu',
      );
      expect(file.path.endsWith('pkg.etu'), isTrue);
      expect(await file.length(), bytes.length);
      expect(File('${file.path}.part').existsSync(), isFalse);
      expect(File('${file.path}.part.json').existsSync(), isFalse);
    });

    test('进度回调收到 received/total', () async {
      final bytes = assetBytes(2048);
      final dio = dioWithServer(bytes);
      final progresses = <int>[];
      await downloader(dio).download(
        asset: assetOf(bytes),
        releaseId: 'rel-1',
        downloadUrl: 'http://localhost:9/pkg.etu',
        onProgress: (received, total) => progresses.add(received),
      );
      expect(progresses, isNotEmpty);
      expect(progresses.last, bytes.length);
    });
  });

  group('续传', () {
    test('已有 partial：发 Range bytes=N-，206 增量追加', () async {
      final bytes = assetBytes(4096);
      final seenHeaders = <Map<String, dynamic>>[];
      final dio = dioWithServer(bytes, requestLog: [
        (options) => seenHeaders.add(options.headers),
      ]);
      final part = File(
          '${tempDir.path}${Platform.pathSeparator}pkg.etu.part');
      part.writeAsBytesSync(bytes.sublist(0, 1024));
      // 手工写 sidecar（身份匹配）。
      File('${part.path}.json').writeAsStringSync(
        '{"assetId":"asset-1","releaseId":"rel-1",'
        '"sha256":"${sha256.convert(bytes).toString()}",'
        '"sizeBytes":${bytes.length},'
        '"strongEtag":"\\"strong-etag\\"","updatedAtMs":'
        '${DateTime.now().millisecondsSinceEpoch}}',
      );

      final file = await downloader(dio).download(
        asset: assetOf(bytes),
        releaseId: 'rel-1',
        downloadUrl: 'http://localhost:9/pkg.etu',
      );
      expect(await file.length(), bytes.length);
      // Range: bytes=1024- 已发出。
      expect(seenHeaders, isNotEmpty);
      expect(seenHeaders.first['Range'], 'bytes=1024-');
      expect(seenHeaders.first['If-Range'], '"strong-etag"');
    });

    test('localPartSize == sizeBytes：不发 Range，先整文件校验', () async {
      final bytes = assetBytes(512);
      final seenHeaders = <Map<String, dynamic>>[];
      final dio = dioWithServer(bytes, requestLog: [
        (options) => seenHeaders.add(options.headers),
      ]);
      final part = File(
          '${tempDir.path}${Platform.pathSeparator}pkg.etu.part');
      part.writeAsBytesSync(bytes); // 完整字节已在本地。
      File('${part.path}.json').writeAsStringSync(
        '{"assetId":"asset-1","releaseId":"rel-1",'
        '"sha256":"${sha256.convert(bytes).toString()}",'
        '"sizeBytes":${bytes.length},'
        '"strongEtag":null,"updatedAtMs":'
        '${DateTime.now().millisecondsSinceEpoch}}',
      );

      final file = await downloader(dio).download(
        asset: assetOf(bytes),
        releaseId: 'rel-1',
        downloadUrl: 'http://localhost:9/pkg.etu',
      );
      expect(await file.length(), bytes.length);
      // 整文件校验通过后直接 rename，不应有任何网络请求。
      expect(seenHeaders, isEmpty);
    });

    test('sidecar 身份漂移（不同 sha）：作废旧 partial 从零开始', () async {
      final bytes = assetBytes(1024);
      final otherBytes = assetBytes(1024);
      final dio = dioWithServer(bytes);
      final part = File(
          '${tempDir.path}${Platform.pathSeparator}pkg.etu.part');
      part.writeAsBytesSync(otherBytes.sublist(0, 100));
      File('${part.path}.json').writeAsStringSync(
        '{"assetId":"asset-1","releaseId":"rel-OTHER",'
        '"sha256":"${sha256.convert(otherBytes).toString()}",'
        '"sizeBytes":${otherBytes.length},'
        '"strongEtag":null,"updatedAtMs":'
        '${DateTime.now().millisecondsSinceEpoch}}',
      );

      final file = await downloader(dio).download(
        asset: assetOf(bytes),
        releaseId: 'rel-1',
        downloadUrl: 'http://localhost:9/pkg.etu',
      );
      // 身份不匹配 → 从零下载完整文件，最终字节正确。
      expect(await file.length(), bytes.length);
      expect(sha256.bind(file.openRead()).first,
          completion(sha256.convert(bytes)));
    });
  });

  group('校验失败 fail closed', () {
    test('本地 partial 长度==sizeBytes 但字节损坏：删 partial 并抛 LOCAL_CORRUPT'
        '（合同 :274 重新 latest，不沿旧 URL 重下）', () async {
      final bytes = assetBytes(512);
      final corrupted = Uint8List.fromList(bytes);
      corrupted[0] ^= 0xFF;
      final part = File(
          '${tempDir.path}${Platform.pathSeparator}pkg.etu.part');
      part.writeAsBytesSync(corrupted);
      File('${part.path}.json').writeAsStringSync(
        '{"assetId":"asset-1","releaseId":"rel-1",'
        '"sha256":"${sha256.convert(bytes).toString()}",'
        '"sizeBytes":${bytes.length},'
        '"strongEtag":null,"updatedAtMs":'
        '${DateTime.now().millisecondsSinceEpoch}}',
      );

      try {
        await downloader(dioWithServer(bytes)).download(
          asset: assetOf(bytes),
          releaseId: 'rel-1',
          downloadUrl: 'http://localhost:9/pkg.etu',
        );
        fail('应抛 LOCAL_CORRUPT');
      } on OtaDownloadException catch (e) {
        expect(e.code, 'LOCAL_CORRUPT');
      }
      // 损坏 partial 与 sidecar 均已删除。
      expect(part.existsSync(), isFalse);
      expect(File('${part.path}.json').existsSync(), isFalse);
    });

    test('localPartSize > sizeBytes：删 partial 并抛 LOCAL_CORRUPT'
        '（合同 :275）', () async {
      final bytes = assetBytes(256);
      final part = File(
          '${tempDir.path}${Platform.pathSeparator}pkg.etu.part');
      part.writeAsBytesSync(List<int>.filled(999, 0));
      File('${part.path}.json').writeAsStringSync(
        '{"assetId":"asset-1","releaseId":"rel-1",'
        '"sha256":"${sha256.convert(bytes).toString()}",'
        '"sizeBytes":${bytes.length},'
        '"strongEtag":null,"updatedAtMs":'
        '${DateTime.now().millisecondsSinceEpoch}}',
      );

      try {
        await downloader(dioWithServer(bytes)).download(
          asset: assetOf(bytes),
          releaseId: 'rel-1',
          downloadUrl: 'http://localhost:9/pkg.etu',
        );
        fail('应抛 LOCAL_CORRUPT');
      } on OtaDownloadException catch (e) {
        expect(e.code, 'LOCAL_CORRUPT');
      }
      expect(part.existsSync(), isFalse);
      expect(File('${part.path}.json').existsSync(), isFalse);
    });
  });

  group('24 小时清理', () {
    test('超时 partial 与 sidecar 被清理；新鲜 partial 保留', () async {
      final freshPart = File(
          '${tempDir.path}${Platform.pathSeparator}fresh.etu.part');
      freshPart.writeAsBytesSync([1, 2, 3]);
      File('${freshPart.path}.json').writeAsStringSync(
        '{"assetId":"a","releaseId":"r","sha256":"'
        '${'a' * 64}","sizeBytes":3,"strongEtag":null,'
        '"updatedAtMs":${DateTime.now().millisecondsSinceEpoch}}',
      );

      final stalePart = File(
          '${tempDir.path}${Platform.pathSeparator}stale.etu.part');
      stalePart.writeAsBytesSync([4, 5, 6]);
      File('${stalePart.path}.json').writeAsStringSync(
        '{"assetId":"b","releaseId":"r","sha256":"'
        '${'b' * 64}","sizeBytes":3,"strongEtag":null,'
        '"updatedAtMs":${DateTime.now()
            .subtract(const Duration(hours: 25))
            .millisecondsSinceEpoch}}',
      );

      await OtaFirmwareDownload(
        dio: Dio(),
        dirProvider: () async => tempDir,
      ).cleanExpiredPartials(tempDir);

      expect(freshPart.existsSync(), isTrue);
      expect(File('${freshPart.path}.json').existsSync(), isTrue);
      expect(stalePart.existsSync(), isFalse);
      expect(File('${stalePart.path}.json').existsSync(), isFalse);
    });

    test('孤儿 partial（无 sidecar）被清理', () async {
      final orphan = File(
          '${tempDir.path}${Platform.pathSeparator}orphan.etu.part');
      orphan.writeAsBytesSync([1]);
      await OtaFirmwareDownload(
        dio: Dio(),
        dirProvider: () async => tempDir,
      ).cleanExpiredPartials(tempDir);
      expect(orphan.existsSync(), isFalse);
    });

    test('孤儿 sidecar（无 .part）与 .tmp 残留被清理', () async {
      final ghostSidecar = File(
          '${tempDir.path}${Platform.pathSeparator}ghost.etu.part.json');
      ghostSidecar.writeAsStringSync(
        '{"assetId":"g","releaseId":"r","sha256":"'
        '${'c' * 64}","sizeBytes":1,"strongEtag":null,'
        '"updatedAtMs":${DateTime.now().millisecondsSinceEpoch}}',
      );
      final tmp = File(
          '${tempDir.path}${Platform.pathSeparator}ghost.etu.part.json.tmp');
      tmp.writeAsStringSync('{}');
      await OtaFirmwareDownload(
        dio: Dio(),
        dirProvider: () async => tempDir,
      ).cleanExpiredPartials(tempDir);
      expect(ghostSidecar.existsSync(), isFalse);
      expect(tmp.existsSync(), isFalse);
    });
  });

  group('PR13 续传响应头校验（fail closed）', () {
    File writePartial(Uint8List bytes, int prefixLen) {
      final part = File(
          '${tempDir.path}${Platform.pathSeparator}pkg.etu.part');
      part.writeAsBytesSync(bytes.sublist(0, prefixLen));
      File('${part.path}.json').writeAsStringSync(
        '{"assetId":"asset-1","releaseId":"rel-1",'
        '"sha256":"${sha256.convert(bytes).toString()}",'
        '"sizeBytes":${bytes.length},'
        '"strongEtag":"\\"strong-etag\\"","updatedAtMs":'
        '${DateTime.now().millisecondsSinceEpoch}}',
      );
      return part;
    }

    test('206 缺 Accept-Ranges 头：作废 partial 从零重下后成功', () async {
      final bytes = assetBytes(2048);
      writePartial(bytes, 1024);
      final dio = dioWithServer(bytes,
          behavior: const _MockBehavior(omitAcceptRanges: true));
      final file = await downloader(dio).download(
        asset: assetOf(bytes),
        releaseId: 'rel-1',
        downloadUrl: 'http://localhost:9/pkg.etu',
      );
      expect(await file.length(), bytes.length);
      expect(sha256.bind(file.openRead()).first,
          completion(sha256.convert(bytes)));
    });

    test('206 Content-Range 区间不符：作废 partial 从零重下后成功', () async {
      final bytes = assetBytes(2048);
      writePartial(bytes, 1024);
      final dio = dioWithServer(bytes,
          behavior: const _MockBehavior(badContentRange: true));
      final file = await downloader(dio).download(
        asset: assetOf(bytes),
        releaseId: 'rel-1',
        downloadUrl: 'http://localhost:9/pkg.etu',
      );
      expect(await file.length(), bytes.length);
    });

    test('206 无强 ETag（If-Range 已发）：作废 partial 从零重下后成功',
        () async {
      final bytes = assetBytes(2048);
      writePartial(bytes, 1024);
      final dio = dioWithServer(bytes,
          behavior: const _MockBehavior(omit206Etag: true));
      final file = await downloader(dio).download(
        asset: assetOf(bytes),
        releaseId: 'rel-1',
        downloadUrl: 'http://localhost:9/pkg.etu',
      );
      expect(await file.length(), bytes.length);
    });

    test('未请求区间却返回 206：作废后仍强制 206 → RESUME_PROTOCOL',
        () async {
      final bytes = assetBytes(2048);
      writePartial(bytes, 1024);
      // 第一轮（带 Range）206 缺 Accept-Ranges → 违规作废从零重下；
      // 第二轮（无 Range）仍强制 206 → 无条件 206 协议违规 fail closed。
      final dio = dioWithServer(bytes,
          behavior: const _MockBehavior(
              omitAcceptRanges: true, force206: true));
      try {
        await downloader(dio).download(
          asset: assetOf(bytes),
          releaseId: 'rel-1',
          downloadUrl: 'http://localhost:9/pkg.etu',
        );
        fail('应抛 RESUME_PROTOCOL');
      } on OtaDownloadException catch (e) {
        expect(e.code, 'RESUME_PROTOCOL');
      }
    });

    test('416：删除 partial 并抛 RANGE_AT_END（上层重新 latest）', () async {
      final bytes = assetBytes(1024);
      final part = writePartial(bytes, 1024); // 本地已完整但走续传检查
      // sidecar 强制续传路径：长度已等于 sizeBytes 时整文件校验直接通过，
      // 因此构造半份 partial + mock 返回 416。
      part.writeAsBytesSync(bytes.sublist(0, 512));
      final dio = dioWithServer(bytes,
          behavior: const _MockBehavior(status416: true));
      try {
        await downloader(dio).download(
          asset: assetOf(bytes),
          releaseId: 'rel-1',
          downloadUrl: 'http://localhost:9/pkg.etu',
        );
        fail('应抛 RANGE_AT_END');
      } on OtaDownloadException catch (e) {
        expect(e.code, 'RANGE_AT_END');
      }
      expect(part.existsSync(), isFalse);
      expect(File('${part.path}.json').existsSync(), isFalse);
    });

    test('401 body TOKEN_EXPIRED：抛 URL_EXPIRED（RC2-11 分流）', () async {
      final bytes = assetBytes(1024);
      final dio = dioWithServer(bytes,
          behavior: const _MockBehavior(
              status: 401, errorBody: '{"errorCode":"TOKEN_EXPIRED"}'));
      try {
        await downloader(dio).download(
          asset: assetOf(bytes),
          releaseId: 'rel-1',
          downloadUrl: 'http://localhost:9/pkg.etu',
        );
        fail('应抛 URL_EXPIRED');
      } on OtaDownloadException catch (e) {
        expect(e.code, 'URL_EXPIRED');
      }
    });

    test('409 ASSET_ARCHIVED：抛 ASSET_CONFLICT（重新 latest 触发器）',
        () async {
      final bytes = assetBytes(1024);
      final dio = dioWithServer(bytes,
          behavior: const _MockBehavior(
              status: 409, errorBody: '{"errorCode":"ASSET_ARCHIVED"}'));
      try {
        await downloader(dio).download(
          asset: assetOf(bytes),
          releaseId: 'rel-1',
          downloadUrl: 'http://localhost:9/pkg.etu',
        );
        fail('应抛 ASSET_CONFLICT');
      } on OtaDownloadException catch (e) {
        expect(e.code, 'ASSET_CONFLICT');
      }
    });

    test('200 Content-Length 与清单不符：抛 RESUME_PROTOCOL', () async {
      final bytes = assetBytes(1024);
      final dio = dioWithServer(bytes,
          behavior: const _MockBehavior(contentLengthOverride: 999));
      try {
        await downloader(dio).download(
          asset: assetOf(bytes),
          releaseId: 'rel-1',
          downloadUrl: 'http://localhost:9/pkg.etu',
        );
        fail('应抛 RESUME_PROTOCOL');
      } on OtaDownloadException catch (e) {
        expect(e.code, 'RESUME_PROTOCOL');
      }
    });
  });

  group('Content-Digest 交叉核对（RFC 9530）', () {
    String digestOf(Uint8List bytes) =>
        'sha-256=:${base64.encode(sha256.convert(bytes).bytes)}:';

    test('正确的 sha-256 digest：下载成功', () async {
      final bytes = assetBytes(1024);
      final dio = dioWithServer(bytes,
          behavior: _MockBehavior(contentDigest: digestOf(bytes)));
      final file = await downloader(dio).download(
        asset: assetOf(bytes),
        releaseId: 'rel-1',
        downloadUrl: 'http://localhost:9/pkg.etu',
      );
      expect(await file.length(), bytes.length);
    });

    test('错误的 digest：抛 DIGEST_MISMATCH', () async {
      final bytes = assetBytes(1024);
      final other = assetBytes(2048);
      final dio = dioWithServer(bytes,
          behavior: _MockBehavior(contentDigest: digestOf(other)));
      try {
        await downloader(dio).download(
          asset: assetOf(bytes),
          releaseId: 'rel-1',
          downloadUrl: 'http://localhost:9/pkg.etu',
        );
        fail('应抛 DIGEST_MISMATCH');
      } on OtaDownloadException catch (e) {
        expect(e.code, 'DIGEST_MISMATCH');
      }
    });

    test('非法 digest 格式（无 sha-256 项）：RESUME_PROTOCOL（RC2-11）',
        () async {
      final bytes = assetBytes(1024);
      // header 存在但只有不支持的算法：不得静默降级为「无校验」。
      final dio = dioWithServer(bytes,
          behavior: const _MockBehavior(contentDigest: 'sha-512=:AAAA:'));
      try {
        await downloader(dio).download(
          asset: assetOf(bytes),
          releaseId: 'rel-1',
          downloadUrl: 'http://localhost:9/pkg.etu',
        );
        fail('应抛 RESUME_PROTOCOL');
      } on OtaDownloadException catch (e) {
        expect(e.code, 'RESUME_PROTOCOL');
      }
    });
  });

  group('RC2 状态分类与响应模式归一', () {
    File writePartial(Uint8List bytes, int prefixLen) {
      final part = File(
          '${tempDir.path}${Platform.pathSeparator}pkg.etu.part');
      part.writeAsBytesSync(bytes.sublist(0, prefixLen));
      File('${part.path}.json').writeAsStringSync(
        '{"assetId":"asset-1","releaseId":"rel-1",'
        '"sha256":"${sha256.convert(bytes).toString()}",'
        '"sizeBytes":${bytes.length},'
        '"strongEtag":"\\"strong-etag\\"","updatedAtMs":'
        '${DateTime.now().millisecondsSinceEpoch}}',
      );
      return part;
    }

    test('401 TOKEN_INVALID：URL_EXPIRED 且 partial 保留供重新签发后续传',
        () async {
      final bytes = assetBytes(2048);
      final part = writePartial(bytes, 1024);
      final dio = dioWithServer(bytes,
          behavior: const _MockBehavior(
              status: 401, errorBody: '{"errorCode":"TOKEN_INVALID"}'));
      try {
        await downloader(dio).download(
          asset: assetOf(bytes),
          releaseId: 'rel-1',
          downloadUrl: 'http://localhost:9/pkg.etu',
        );
        fail('应抛 URL_EXPIRED');
      } on OtaDownloadException catch (e) {
        expect(e.code, 'URL_EXPIRED');
      }
      // 401 TOKEN_* 不删本地 metadata（资产字节未变）。
      expect(part.existsSync(), isTrue);
      expect(File('${part.path}.json').existsSync(), isTrue);
    });

    test('401 未知 errorCode：HTTP_STATUS fail closed', () async {
      final bytes = assetBytes(1024);
      final dio = dioWithServer(bytes,
          behavior: const _MockBehavior(
              status: 401, errorBody: '{"errorCode":"WHAT_IS_THIS"}'));
      try {
        await downloader(dio).download(
          asset: assetOf(bytes),
          releaseId: 'rel-1',
          downloadUrl: 'http://localhost:9/pkg.etu',
        );
        fail('应抛 HTTP_STATUS');
      } on OtaDownloadException catch (e) {
        expect(e.code, 'HTTP_STATUS');
      }
    });

    test('401 空 body：HTTP_STATUS fail closed', () async {
      final bytes = assetBytes(1024);
      final dio = dioWithServer(bytes,
          behavior: const _MockBehavior(status: 401));
      try {
        await downloader(dio).download(
          asset: assetOf(bytes),
          releaseId: 'rel-1',
          downloadUrl: 'http://localhost:9/pkg.etu',
        );
        fail('应抛 HTTP_STATUS');
      } on OtaDownloadException catch (e) {
        expect(e.code, 'HTTP_STATUS');
      }
    });

    test('410 ASSET_DISABLED：URL_EXPIRED 且 partial 删除（本地 metadata '
        '作废）', () async {
      final bytes = assetBytes(2048);
      final part = writePartial(bytes, 1024);
      final dio = dioWithServer(bytes,
          behavior: const _MockBehavior(
              status: 410, errorBody: '{"errorCode":"ASSET_DISABLED"}'));
      try {
        await downloader(dio).download(
          asset: assetOf(bytes),
          releaseId: 'rel-1',
          downloadUrl: 'http://localhost:9/pkg.etu',
        );
        fail('应抛 URL_EXPIRED');
      } on OtaDownloadException catch (e) {
        expect(e.code, 'URL_EXPIRED');
      }
      expect(part.existsSync(), isFalse);
      expect(File('${part.path}.json').existsSync(), isFalse);
    });

    test('409 ASSET_ARCHIVED：ASSET_CONFLICT 且 partial 保留', () async {
      final bytes = assetBytes(2048);
      final part = writePartial(bytes, 1024);
      final dio = dioWithServer(bytes,
          behavior: const _MockBehavior(
              status: 409, errorBody: '{"errorCode":"ASSET_ARCHIVED"}'));
      try {
        await downloader(dio).download(
          asset: assetOf(bytes),
          releaseId: 'rel-1',
          downloadUrl: 'http://localhost:9/pkg.etu',
        );
        fail('应抛 ASSET_CONFLICT');
      } on OtaDownloadException catch (e) {
        expect(e.code, 'ASSET_CONFLICT');
      }
      // 409 服务端状态冲突：资产字节未变，partial 保留。
      expect(part.existsSync(), isTrue);
      expect(File('${part.path}.json').existsSync(), isTrue);
    });

    test('If-Range 失配回退 200 完整 body：截断旧 partial 重下成功'
        '（RC2-10：期望剩余量在归一后计算）', () async {
      final bytes = assetBytes(2048);
      writePartial(bytes, 1024);
      final dio = dioWithServer(bytes,
          behavior: const _MockBehavior(rangeReturns200: true));
      final file = await downloader(dio).download(
        asset: assetOf(bytes),
        releaseId: 'rel-1',
        downloadUrl: 'http://localhost:9/pkg.etu',
      );
      // 200 回退后 expectedRemaining 必须是整文件大小：旧实现按
      // 旧剩余量（1024）校验会在收满 2048 后误报 LENGTH_MISMATCH。
      expect(await file.length(), bytes.length);
      expect(sha256.bind(file.openRead()).first,
          completion(sha256.convert(bytes)));
    });
  });

  group('RC3-10/11 看码分流与资源释放', () {
    File writePartial(Uint8List bytes, int prefixLen) {
      final part = File(
          '${tempDir.path}${Platform.pathSeparator}pkg.etu.part');
      part.writeAsBytesSync(bytes.sublist(0, prefixLen));
      File('${part.path}.json').writeAsStringSync(
        '{"assetId":"asset-1","releaseId":"rel-1",'
        '"sha256":"${sha256.convert(bytes).toString()}",'
        '"sizeBytes":${bytes.length},'
        '"strongEtag":"\\"strong-etag\\"","updatedAtMs":'
        '${DateTime.now().millisecondsSinceEpoch}}',
      );
      return part;
    }

    test('409/410 空错误体：HTTP_STATUS fail closed，不猜测刷新、'
        'partial 保留（看码分流）', () async {
      final bytes = assetBytes(2048);
      for (final status in [409, 410]) {
        final part = writePartial(bytes, 1024);
        final dio = dioWithServer(bytes,
            behavior: _MockBehavior(status: status));
        try {
          await downloader(dio).download(
            asset: assetOf(bytes),
            releaseId: 'rel-1',
            downloadUrl: 'http://localhost:9/pkg.etu',
          );
          fail('HTTP $status 空体应抛 HTTP_STATUS');
        } on OtaDownloadException catch (e) {
          // 空体无稳定 errorCode：不得按状态码猜测 ASSET_ARCHIVED/
          // ASSET_DISABLED 触发刷新——按裸状态码闭锁。
          expect(e.code, 'HTTP_STATUS', reason: 'HTTP $status 空体');
          expect(e.httpStatus, status);
          expect(e.httpError, isNull, reason: '空体不得伪造 OtaHttpError');
        }
        // 本地 partial 字节仍对应该资产：未知码不作废 metadata。
        expect(part.existsSync(), isTrue, reason: 'HTTP $status 空体');
        expect(File('${part.path}.json').existsSync(), isTrue);
      }
    });

    test('400/426 非受控状态：Dio badResponse 统一转换 HTTP_STATUS（RC3-10）',
        () async {
      final bytes = assetBytes(1024);
      for (final status in [400, 426]) {
        final dio = dioWithServer(bytes,
            behavior: _MockBehavior(status: status));
        try {
          await downloader(dio).download(
            asset: assetOf(bytes),
            releaseId: 'rel-1',
            downloadUrl: 'http://localhost:9/pkg.etu',
          );
          fail('HTTP $status 应抛 HTTP_STATUS');
        } on OtaDownloadException catch (e) {
          // validateStatus 只放行 401/409/410/416，其余 4xx 走 Dio
          // badResponse——必须统一归 OtaDownloadException 语义，
          // 不得作为裸 DioException 漏到 generic 路径洗成普通网络失败。
          expect(e.code, 'HTTP_STATUS', reason: 'HTTP $status');
          expect(e.httpStatus, status);
        }
      }
    });

    test('401 错误体超 64KB：有界读取按裸状态码 fail closed，'
        '不按前缀猜 TOKEN_*（RC3-11）', () async {
      final bytes = assetBytes(1024);
      // 超大错误体：JSON 前缀是 TOKEN_EXPIRED 但整体不可在 64KB 内
      // 完成——有界读取必须整体拒绝（overflow → null），不得解析
      // 截断前缀把授权过期误判成可刷新。
      final hugeBody =
          '{"errorCode":"TOKEN_EXPIRED","pad":"${'A' * (128 * 1024)}"}';
      final dio = dioWithServer(bytes,
          behavior: _MockBehavior(status: 401, errorBody: hugeBody));
      try {
        await downloader(dio).download(
          asset: assetOf(bytes),
          releaseId: 'rel-1',
          downloadUrl: 'http://localhost:9/pkg.etu',
        );
        fail('超大错误体应抛 HTTP_STATUS');
      } on OtaDownloadException catch (e) {
        expect(e.code, 'HTTP_STATUS');
        expect(e.httpStatus, 401);
      }
    });

    test('sidecar 强 ETag 内部未转义引号：不信任续传身份，从零重下'
        '（RC3-11 sidecar 侧校验）', () async {
      final bytes = assetBytes(2048);
      final part = File(
          '${tempDir.path}${Platform.pathSeparator}pkg.etu.part');
      part.writeAsBytesSync(bytes.sublist(0, 1024));
      // sidecar 携带非法强 ETag（内部未转义引号，RFC 7232 不合法）：
      // 读取侧必须按无有效 ETag 处理——作废旧 partial 从零开始，
      // 不得把它放进 If-Range。
      File('${part.path}.json').writeAsStringSync(
        '{"assetId":"asset-1","releaseId":"rel-1",'
        '"sha256":"${sha256.convert(bytes).toString()}",'
        '"sizeBytes":${bytes.length},'
        '"strongEtag":"\\"bad\\"etag\\"","updatedAtMs":'
        '${DateTime.now().millisecondsSinceEpoch}}',
      );
      final seenHeaders = <Map<String, dynamic>>[];
      final dio = dioWithServer(bytes, requestLog: [
        (options) => seenHeaders.add(options.headers),
      ]);
      final file = await downloader(dio).download(
        asset: assetOf(bytes),
        releaseId: 'rel-1',
        downloadUrl: 'http://localhost:9/pkg.etu',
      );
      expect(await file.length(), bytes.length);
      expect(seenHeaders.first['Range'], isNull,
          reason: '坏 ETag 不得作为续传身份发 Range');
      expect(seenHeaders.first['If-Range'], isNull);
    });

    test('206 响应 ETag 内部未转义引号：强校验拒绝 → 作废 partial '
        '从零重下（RC3-11 响应侧校验）', () async {
      final bytes = assetBytes(2048);
      writePartial(bytes, 1024);
      final seenHeaders = <Map<String, dynamic>>[];
      final dio = dioWithServer(
        bytes,
        etag: '"bad"etag"', // 非法强 ETag：不得通过 _isStrongEtag
        requestLog: [(options) => seenHeaders.add(options.headers)],
      );
      final file = await downloader(dio).download(
        asset: assetOf(bytes),
        releaseId: 'rel-1',
        downloadUrl: 'http://localhost:9/pkg.etu',
      );
      expect(await file.length(), bytes.length);
      // 第一轮带 Range/If-Range；206 响应 ETag 非强 → 头校验违规作废
      // 重来；第二轮从零（无 Range）。
      expect(seenHeaders.length, 2);
      expect(seenHeaders.first['Range'], 'bytes=1024-');
      expect(seenHeaders.last['Range'], isNull);
      expect(sha256.bind(file.openRead()).first,
          completion(sha256.convert(bytes)));
    });

    test('早退路径有界 drain：Content-Length 不符只消费 ≤64KB+1 片，'
        '不以整流排空为代价（RC3-11）', () async {
      // 256KB body 分 16KB 片投递；200 Content-Length 与清单不符触发
      // 早退 drain——有界消费在读满 64KB 后取消订阅，未投递分片不再
      // 被拉取（async* 生成器停在 yield 处）。无界 drain 会拉满 256KB。
      final bytes = assetBytes(256 * 1024);
      final dio = dioWithServer(bytes,
          behavior: const _MockBehavior(
              contentLengthOverride: 999, bodyChunkSize: 16 * 1024));
      final token = CancelToken();
      try {
        await downloader(dio).download(
          asset: assetOf(bytes),
          releaseId: 'rel-1',
          downloadUrl: 'http://localhost:9/pkg.etu',
          cancelToken: token,
        );
        fail('应抛 RESUME_PROTOCOL');
      } on OtaDownloadException catch (e) {
        expect(e.code, 'RESUME_PROTOCOL');
      }
      final adapter = dio.httpClientAdapter as _MockAdapter;
      expect(
        adapter.deliveredBytes,
        lessThanOrEqualTo(64 * 1024 + 2 * 16 * 1024),
        reason: 'drain 必须有界：超限一至两片的调度余量外不得继续消费',
      );
      expect(adapter.deliveredBytes, lessThan(256 * 1024));
      // RC3-11⑤：达界 break 只取消 Dio 的包装流——锁定的 Dio 5.9.0
      // handleResponseStream 不把包装流 onCancel 传回底层 source，
      // 底层响应仍可能被继续读取。达界必须让 Dio 层真正中止底层请求，
      // 观测点是 adapter 侧的 cancelFuture（真实 adapter 在此 abort 连接）。
      await Future<void>.delayed(Duration.zero);
      expect(adapter.abortedRequests, 1,
          reason: 'drain 达界后必须真正中止底层请求，而不只是本端停读');
      // 中止本次响应 ≠ 用户取消整个下载：会话 token 必须保持干净，
      // 否则紧随的重下会立刻 CANCELLED，把服务器协议违规误报成用户取消。
      expect(token.isCancelled, isFalse,
          reason: '协议违规不得连带取消会话 token');
    });

    test('首块正文停滞：包装流空闲超时兜底，不无限挂起（RC3-11⑤）',
        () async {
      // 响应头已到、首块正文永不到（stallAfterChunks: 0 → 首块前停滞，
      // fake 不投递任何 data 事件）——Dio 5.9.0 的接收空闲计时器只在
      // 收到首个 data 事件后启动，此时不触发；裸 await for 会无限挂起。
      // 对包装流套 Stream.timeout 后必须在 receiveIdleTimeout 内注入
      // TimeoutException 终止等待。修复缺失时表现为用例超时挂起而非
      // 安静通过。首块前停滞使包装流空闲超时成为唯一超时来源，测试
      // 不会因 Dio 内部 receiveTimer 先到而失去鉴别力。
      final bytes = assetBytes(4096);
      final dio = dioWithServer(bytes,
          behavior: const _MockBehavior(
              bodyChunkSize: 1024, stallAfterChunks: 0));
      dio.options.receiveTimeout = const Duration(milliseconds: 200);
      try {
        await downloader(dio).download(
          asset: assetOf(bytes),
          releaseId: 'rel-1',
          downloadUrl: 'http://localhost:9/pkg.etu',
        );
        fail('应超时中止');
      } on TimeoutException {
        // 停滞界生效：按网络中断类失败处置。
      }
      // 网络中断语义：partial 保留供下次续传，不删除。
      final part =
          File('${tempDir.path}${Platform.pathSeparator}pkg.etu.part');
      expect(part.existsSync(), isTrue,
          reason: '停滞按网络中断处置，partial 保留供续传');
      expect(await part.length(), 0,
          reason: '首块前停滞，无字节落盘（openWrite 已创建文件）');
    }, timeout: const Timeout(Duration(seconds: 10)));

    test('首个 206 头违规：旧响应被真正中止，且从零重下仍成功'
        '（RC3-11⑤ attempt token）', () async {
      // 256KB 资产 + 本地 128KB partial → 首轮 206 缺 Accept-Ranges（头
      // 违规，不进入写盘）→ 有界 drain 达界必须中止**这一次**响应；随后
      // 作废 partial 从零重下必须照常成功。
      // 鉴别力（两个方向都能打红）：
      // - 旧实现首次违规传 null token（为了不污染重下），旧连接不关，
      //   abortedRequests=0；
      // - 若改用会话 token 去关旧响应，重下立刻 CANCELLED，download 抛异常。
      final bytes = assetBytes(256 * 1024);
      writePartial(bytes, 128 * 1024);
      final seenHeaders = <Map<String, dynamic>>[];
      final dio = dioWithServer(
        bytes,
        behavior: const _MockBehavior(
            omitAcceptRanges: true, bodyChunkSize: 16 * 1024),
        requestLog: [(options) => seenHeaders.add(options.headers)],
      );
      final file = await downloader(dio).download(
        asset: assetOf(bytes),
        releaseId: 'rel-1',
        downloadUrl: 'http://localhost:9/pkg.etu',
      );
      expect(await file.length(), bytes.length);
      expect(sha256.bind(file.openRead()).first,
          completion(sha256.convert(bytes)));
      expect(seenHeaders.length, 2);
      expect(seenHeaders.first['Range'], 'bytes=131072-');
      expect(seenHeaders.last['Range'], isNull, reason: '第二轮从零重下');
      await Future<void>.delayed(Duration.zero);
      final adapter = dio.httpClientAdapter as _MockAdapter;
      expect(adapter.abortedRequests, 1,
          reason: '首个违规响应必须被中止，且只中止它一个');
    }, timeout: const Timeout(Duration(seconds: 30)));

    test('错误体零事件停滞：空闲超时兜底并中止上游，不无限挂起（RC3-11⑥）',
        () async {
      // 401 响应头已到、错误体一个 data 事件都不来。Dio 的接收空闲计时器
      // 只在首个 data 事件后启动，此处永不启动；裸 await for 会让 401/409/
      // 410 的看码分流永久挂起，且挂在 await 上连取消都到不了。修复缺失
      // 时表现为用例超时挂起，而不是安静通过。
      final bytes = assetBytes(1024);
      final dio = dioWithServer(bytes,
          behavior: const _MockBehavior(
              status: 401,
              errorBody: '{"errorCode":"TOKEN_EXPIRED"}',
              bodyChunkSize: 1024,
              stallAfterChunks: 0));
      dio.options.receiveTimeout = const Duration(milliseconds: 200);
      try {
        await downloader(dio).download(
          asset: assetOf(bytes),
          releaseId: 'rel-1',
          downloadUrl: 'http://localhost:9/pkg.etu',
        );
        fail('停滞的 401 错误体应按坏体 fail closed');
      } on OtaDownloadException catch (e) {
        // 读不到 errorCode（停滞按坏体）→ 不得猜成 URL_EXPIRED 触发刷新，
        // 按裸状态码闭锁。
        expect(e.code, 'HTTP_STATUS');
        expect(e.httpStatus, 401);
        expect(e.httpError, isNull, reason: '停滞体不得伪造 OtaHttpError');
      }
      await Future<void>.delayed(Duration.zero);
      final adapter = dio.httpClientAdapter as _MockAdapter;
      expect(adapter.abortedRequests, 1,
          reason: '停滞必须中止上游，不能只退出本端等待');
    }, timeout: const Timeout(Duration(seconds: 10)));

    test('无在途下载时 cancel：既有 partial/sidecar 照常删除（RC3-05⑥）',
        () async {
      // 下载早已结束（或从未开始）时取消不能退化成静默 no-op：用户看到
      // "已取消"，字节却要留到 24h 兜底才清。无在途 = 无并发写盘方，
      // 删除是安全且必须的。
      final bytes = assetBytes(2048);
      final part = writePartial(bytes, 1024);
      final sidecar = File('${part.path}.json');
      await downloader(dioWithServer(bytes)).cancel('asset-1');
      expect(part.existsSync(), isFalse,
          reason: '无在途写盘方，取消必须真的删除 partial');
      expect(sidecar.existsSync(), isFalse);
    });

    test('无在途下载时 cancel(keepPartial)：字节保留供续传（RC3-05⑥）',
        () async {
      final bytes = assetBytes(2048);
      final part = writePartial(bytes, 1024);
      await downloader(dioWithServer(bytes))
          .cancel('asset-1', keepPartial: true);
      expect(part.existsSync(), isTrue,
          reason: 'keepPartial 语义不因无在途而改变');
      expect(File('${part.path}.json').existsSync(), isTrue);
    });

    test('body 传输中取消：等在途写盘方退出后再删 partial（RC3-05）',
        () async {
      // 首块已进写盘路径、后续停滞 → 取消到达时写盘方正卡在读流上。
      // cancel 必须先等它退出（sink 已关闭）再删，删除与追加写不得并发；
      // 鉴别力：去掉有界等待直接删，则 cancel 返回时在途尚未退出，
      // pendingError 仍为 null 而红。
      // receiveTimeout 收紧到 2s：无论"取消唤醒读流"还是"空闲超时兜底"
      // 先生效，在途都必然在 cancel 的 5s 有界等待内退出，用例不依赖
      // Dio 内部把包装流取消回传底层 source 的实现细节。
      final bytes = assetBytes(4096);
      final dio = dioWithServer(bytes,
          behavior: const _MockBehavior(
              bodyChunkSize: 1024, stallAfterChunks: 1));
      dio.options.receiveTimeout = const Duration(seconds: 2);
      final owner = downloader(dio);
      final firstChunk = Completer<void>();
      final pending = owner.download(
        asset: assetOf(bytes),
        releaseId: 'rel-1',
        downloadUrl: 'http://localhost:9/pkg.etu',
        onProgress: (received, total) {
          if (!firstChunk.isCompleted) firstChunk.complete();
        },
      );
      // 在途 future 以取消异常退出，错误由本用例接管（不得漏成未捕获）。
      Object? pendingError;
      unawaited(pending.catchError((Object e) {
        pendingError = e;
        return File('${tempDir.path}${Platform.pathSeparator}unused');
      }));
      await firstChunk.future;
      final part =
          File('${tempDir.path}${Platform.pathSeparator}pkg.etu.part');
      expect(part.existsSync(), isTrue);
      await owner.cancel('asset-1');
      await Future<void>.delayed(Duration.zero);
      expect(pendingError, isNotNull, reason: '取消必须让在途路径退出');
      expect(part.existsSync(), isFalse,
          reason: '在途退出后必须删除 partial');
      expect(File('${part.path}.json').existsSync(), isFalse);
    }, timeout: const Timeout(Duration(seconds: 20)));

    test('在途未退出：cancel 有界等待超时后不删，清理回退给下载路径'
        '（RC3-05⑤）', () async {
      // 构造"已登记在途但尚未退出"的窗口：dirProvider 挂起 → download 卡在
      // 解析目录（_inFlight 已登记）。cancel 的 5s 有界等待必然超时——此时
      // 无法证明写盘方已退出，删除既可能失败也不代表清理完成，必须不删，
      // 交给 download 自身退出路径与 24h 兜底。
      // 反向鉴别：把 RC3-05⑥ 的"无在途即删"过度修成"一律删"，此用例红。
      final bytes = assetBytes(2048);
      final part = writePartial(bytes, 1024);
      final gate = Completer<void>();
      final owner = OtaFirmwareDownload(
        dio: dioWithServer(bytes),
        dirProvider: () async {
          await gate.future;
          return tempDir;
        },
      );
      final pending = owner.download(
        asset: assetOf(bytes),
        releaseId: 'rel-1',
        downloadUrl: 'http://localhost:9/pkg.etu',
      );
      final started = DateTime.now();
      await owner.cancel('asset-1');
      expect(DateTime.now().difference(started).inSeconds,
          greaterThanOrEqualTo(4),
          reason: '有界等待必须真的等到上限，不是立即放弃');
      expect(part.existsSync(), isTrue,
          reason: '写盘方未证明退出前不得删除 partial');
      expect(File('${part.path}.json').existsSync(), isTrue);
      // 放行在途路径：它继续按续传完成，证明 cancel 未破坏其状态。
      gate.complete();
      final file = await pending;
      expect(await file.length(), bytes.length);
    }, timeout: const Timeout(Duration(seconds: 30)));

    test('Content-Digest 重复 sha-256 项：RESUME_PROTOCOL（RFC 9530 唯一项）',
        () async {
      final bytes = assetBytes(1024);
      final d = 'sha-256=:${base64.encode(sha256.convert(bytes).bytes)}:';
      final dio = dioWithServer(bytes,
          behavior: _MockBehavior(contentDigest: '$d, $d'));
      try {
        await downloader(dio).download(
          asset: assetOf(bytes),
          releaseId: 'rel-1',
          downloadUrl: 'http://localhost:9/pkg.etu',
        );
        fail('应抛 RESUME_PROTOCOL');
      } on OtaDownloadException catch (e) {
        expect(e.code, 'RESUME_PROTOCOL');
      }
    });

    test('Content-Digest 非规范 base64（长度不足）：RESUME_PROTOCOL',
        () async {
      final bytes = assetBytes(1024);
      final dio = dioWithServer(bytes,
          behavior: const _MockBehavior(contentDigest: 'sha-256=:AAAA:'));
      try {
        await downloader(dio).download(
          asset: assetOf(bytes),
          releaseId: 'rel-1',
          downloadUrl: 'http://localhost:9/pkg.etu',
        );
        fail('应抛 RESUME_PROTOCOL');
      } on OtaDownloadException catch (e) {
        expect(e.code, 'RESUME_PROTOCOL');
      }
    });
  });
}

/// 可注入的服务器行为（默认全部关闭 = 完全合规的 Range 服务器）。
class _MockBehavior {
  const _MockBehavior({
    this.omitAcceptRanges,
    this.omit206Etag,
    this.badContentRange,
    this.force206,
    this.status,
    this.errorBody,
    this.status416,
    this.rangeReturns200,
    this.contentLengthOverride,
    this.contentDigest,
    this.bodyChunkSize,
    this.stallAfterChunks,
  });

  /// 206 响应缺 Accept-Ranges: bytes 头。
  final bool? omitAcceptRanges;

  /// 206 响应缺 ETag 头（If-Range 已发时违规）。
  final bool? omit206Etag;

  /// Content-Range 返回错误起点区间。
  final bool? badContentRange;

  /// 无 Range 请求也强制回 206（构造第二次续传违规）。
  final bool? force206;

  /// 直接返回该 HTTP 状态码（默认空 body）。
  final int? status;

  /// [status] 分支的错误响应体（401 errorCode 分流用）。
  final String? errorBody;

  /// 对任何 Range 请求回 416。
  final bool? status416;

  /// 带 Range 请求也回 200 完整 body（If-Range 失配回退，RC2-10）。
  final bool? rangeReturns200;

  /// 覆盖 Content-Length 头。
  final int? contentLengthOverride;

  /// 附加 Content-Digest 头（RFC 9530）。
  final String? contentDigest;

  /// 把成功 body 切成该大小的片投递（默认单片整发）。用于观测
  /// 早退路径的有界消费：async* 生成器在订阅取消后停在 yield 处，
  /// 未投递分片不再被拉取。
  final int? bodyChunkSize;

  /// 投递这么多片后永久停滞（连接保持但正文不再到达，模拟首块
  /// 停滞/服务器挂起）。仅配合 [bodyChunkSize] 使用。
  final int? stallAfterChunks;
}

/// 简化 mock adapter：按请求 Range 头返回 200 或 206。
class _MockAdapter implements HttpClientAdapter {
  _MockAdapter(this.bytes, this.etag, this.requestLog, this.behavior);

  final Uint8List bytes;
  final String etag;
  final List<void Function(RequestOptions)> requestLog;
  final _MockBehavior behavior;

  /// 已投递给消费方的 body 字节数（yield 前计数；订阅取消后停止）。
  /// 有界 drain 判定的直接观测：无界 drain 会拉满整个 body。
  int deliveredBytes = 0;

  /// Dio 把取消传到 adapter（cancelFuture 触发）的次数。
  ///
  /// RC3-11⑤：真实 IOHttpClientAdapter 在 cancelFuture 触发时 abort 底层
  /// 连接——「上游是否真被关闭」只能在 adapter 侧观测。断言调用方 token
  /// 的标志位不等价：每次尝试改持独立 attempt token 后，会话 token 保持
  /// 未取消（否则协议违规会被误报成用户取消），而底层响应确实已中止。
  int abortedRequests = 0;

  /// 按 [chunkSize] 分片投递 body；片在 yield 前计入 [deliveredBytes]。
  ///
  /// - [cancelFuture] 是 Dio adapter 契约的一部分：真实
  ///   IOHttpClientAdapter 在其触发时 abort 底层请求；mock 同样必须
  ///   响应（置位后生成器停止投递），否则 cancel 语义在 fake 上失真
  ///   （修复前无视 cancelFuture，drain 达界 cancel 后仍全量产出，
  ///   deliveredBytes 观测不能反映有界性）。
  /// - [stallAfterChunks] 在 yield **前**判定：0 表示首块前停滞
  ///   （响应头已到、首个正文事件永不到——Dio receiveTimer 不启动，
  ///   产品的包装流空闲超时是唯一超时来源）；N>0 表示投递 N 片后停滞。
  Stream<Uint8List> _bodyStream(Uint8List body, Future<void>? cancelFuture) {
    final chunkSize = behavior.bodyChunkSize;
    if (chunkSize == null) {
      return Stream<Uint8List>.fromIterable([body]);
    }
    return () async* {
      var cancelled = false;
      if (cancelFuture != null) {
        // ignore: unawaited_futures
        cancelFuture.then((_) {
          cancelled = true;
        });
      }
      var emitted = 0;
      for (var i = 0; i < body.length; i += chunkSize) {
        if (cancelled) {
          return;
        }
        final stallAt = behavior.stallAfterChunks;
        if (stallAt != null && emitted >= stallAt) {
          // 永不完成的等待：模拟服务器停止投递正文（连接保持但不
          // 出数据）。
          await Completer<void>().future;
        }
        final chunk =
            Uint8List.sublistView(body, i, math.min(i + chunkSize, body.length));
        deliveredBytes += chunk.length;
        yield chunk;
        emitted++;
        // 真实 IO 的 chunk 之间存在时隙；本地内存流必须显式补上。
        // async* 的 yield 在消费端未 pause 时同步继续（Dart 语义：仅
        // paused 时挂起），连片 yield 不产生微任务边界——Dio pipe 全速
        // 拉源头时 cancelFuture.then 的回调永远排不上，cancel 语义在
        // fake 上失真（16 片一口气连发后才见置位，有界 drain 断言必红）。
        await Future<void>.delayed(Duration.zero);
      }
    }();
  }

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    for (final log in requestLog) {
      log(options);
    }
    if (cancelFuture != null) {
      // 真实 adapter 在此 abort 底层连接；mock 记账供断言观测。
      // ignore: unawaited_futures
      cancelFuture.then((_) {
        abortedRequests++;
      });
    }
    if (behavior.status != null) {
      if (behavior.stallAfterChunks != null) {
        // 只发头不发体的错误响应：错误体读取路径的零事件停滞。
        // Dio 的接收空闲计时器要等首个 data 事件才启动，此处永不启动，
        // 裸 await for 会无限挂起（产品侧需自带空闲超时兜底）。
        return ResponseBody(
          _bodyStream(
              Uint8List.fromList(utf8.encode(behavior.errorBody ?? '')),
              cancelFuture),
          behavior.status!,
        );
      }
      return ResponseBody.fromString(
          behavior.errorBody ?? '', behavior.status!);
    }
    final range = options.headers['Range'] as String?;
    var start = 0;
    var status = 200;
    if (range != null && range.startsWith('bytes=')) {
      final n = int.tryParse(range.substring(6).split('-').first);
      if (n != null && n < bytes.length) {
        start = n;
        status = 206;
      } else if (n != null && n >= bytes.length) {
        return ResponseBody.fromString('', 416);
      }
    }
    if (behavior.rangeReturns200 == true && status == 206) {
      // If-Range 失配：服务器忽略区间，回 200 完整 body。
      start = 0;
      status = 200;
    }
    if (behavior.force206 == true) {
      status = 206;
    }
    if (behavior.status416 == true && status == 206) {
      return ResponseBody.fromString('', 416);
    }
    final body = bytes.sublist(start);
    final stream = _bodyStream(body, cancelFuture);
    final contentLength =
        behavior.contentLengthOverride ?? body.length;
    return ResponseBody(stream, status, headers: {
      if (behavior.omit206Etag != true || status != 206) 'etag': [etag],
      'content-length': ['$contentLength'],
      if (status == 206 &&
          behavior.omitAcceptRanges != true) ...{
        'accept-ranges': ['bytes'],
      },
      if (status == 206)
        'content-range': [
          behavior.badContentRange == true
              ? 'bytes ${start + 7}-${bytes.length - 1}/${bytes.length}'
              : 'bytes $start-${bytes.length - 1}/${bytes.length}',
        ],
      if (behavior.contentDigest != null)
        'content-digest': [behavior.contentDigest!],
    });
  }

  @override
  void close({bool force = false}) {}
}
