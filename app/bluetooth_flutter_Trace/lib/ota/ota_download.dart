import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:crypto/crypto.dart';
import 'package:dio/dio.dart';

import 'ota_firmware_latest.dart';

/// 固件包下载 owner（冻结依据 docs/ota-cross-system-contracts.md
/// OTA-XC-HTTP-DOWNLOAD、OTA-XC-HTTP-RESUME、OTA-XC-CANCEL-RECOVERY）。
///
/// 职责：
/// - sidecar 原子记录 asset 身份（assetId/releaseId/sha256/sizeBytes/强 ETag/时间）；
/// - `.part` 断点续传（单区间 `Range: bytes=N-`）；
/// - 206 响应必须通过完整头校验集（Accept-Ranges/Content-Range/
///   Content-Length/与 If-Range 一致的强 ETag），违规作废 partial 从零重下；
/// - 200（含 If-Range 失配回退）必须先截断旧 partial；新响应无强 ETag 时
///   不得沿用旧 ETag；
/// - `localPartSize==sizeBytes` 不发 Range，先整文件校验；
/// - 416 → 删除 partial 并抛 `RANGE_AT_END`（上层重新 latest）；
///   401 按 body errorCode 分流（TOKEN_* → `URL_EXPIRED` 不删 partial，
///   未知 → `HTTP_STATUS`）；410 → 删 partial + `URL_EXPIRED`；
///   409 → `ASSET_CONFLICT` 不删 partial；
/// - 本地 partial 损坏/超长（合同 :274/:275）→ 删 partial + `LOCAL_CORRUPT`
///   （上层重新 latest，不沿旧 URL 重下）；
/// - Content-Digest（RFC 9530）存在时对实收字节交叉核对；
/// - 完成前同时验证长度与 metadata `sha256`，然后原子 rename；
/// - 24 小时 partial 清理（含孤儿 sidecar）。
class OtaFirmwareDownload {
  OtaFirmwareDownload({Dio? dio, this.dirProvider, this.stillOwns}) : _dio = dio ?? Dio();

  final Dio _dio;
  /// 返回存放 `.part`/sidecar/最终文件的目录（通常是应用文档目录）。
  final Future<Directory> Function()? dirProvider;

  /// 「本 attempt 仍拥有该资产文件」的判定（RC3-04/05），由上层提供。
  ///
  /// 取消清理要遍历目录、读取 sidecar、逐个删除，全程有 await；取消后
  /// 用户可能立刻重新下载同一资产（新 attempt 写出同名 `.part`/sidecar），
  /// 迟到的枚举会把新 attempt 刚写的字节删掉——按 assetId 匹配挡不住，
  /// 两次 attempt 的 assetId 本来就相同。判定必须在**删除边界**上复核，
  /// 而不是在进入清理时判定一次。
  ///
  /// 为 null 表示调用方不参与归属（单 attempt 场景），清理照常执行。
  final bool Function()? stillOwns;

  final _cancelTokens = <String, CancelToken>{};

  /// 在途 download future（按 assetId），[cancel] 有界等待用（RC3-05）。
  final _inFlight = <String, Future<File>>{};
  /// 用户取消时是否保留已下载字节（由 [cancel] 设置，RC2-04）。
  bool _cancelKeepsPartial = false;

  /// 取消时有界等待在途退出的上限（RC3-05）。
  static const Duration cancelSettleTimeout = Duration(seconds: 5);

  /// 在途未在上限内退出时登记的延后清理（RC3-05⑤）。
  ///
  /// 上层（OtaService.cancelUpgrade）在 owner 退出后 await 它把删除做完；
  /// 归属判定仍按 [stillOwns] 在删除边界复核，新 attempt 接管时不清。
  Future<void>? _deferredCleanup;

  /// 下载（或续传）指定资产，返回最终文件路径。
  ///
  /// 网络失败保留 `.part` 与 sidecar（下次可续传）；用户显式取消走
  /// [cancel]（删除 partial 与 sidecar）。长度或 SHA-256 校验失败按
  /// 产品失败抛 [OtaDownloadException] 并清理损坏 partial，不返回假成功。
  Future<File> download({
    required OtaFirmwareAsset asset,
    required String releaseId,
    required String downloadUrl,
    void Function(int received, int total)? onProgress,
    CancelToken? cancelToken,
  }) {
    // RC3-05：登记在途 future，[cancel] 有界等待其退出（sink 已关闭、
    // 不再写盘）后再删除 partial，避免删除与追加写并发。
    //
    // RC3-02：令牌必须与在途登记在**同一同步段**建立。原实现在
    // _downloadImpl 走完 _resolveDir/cleanExpiredPartials 之后才登记令牌，
    // 这段窗口里的 cancel() 既看不到令牌（无可取消），又因在途 future
    // 尚未结算而在有界等待后放弃删除；impl 随后照常发起请求，用户的取消
    // 被静默吞掉、整包继续下完。前置登记后，任何能看到在途 future 的
    // 取消都必然能看到令牌。
    final token = cancelToken ?? CancelToken();
    _cancelTokens[asset.assetId] = token;
    final future = _downloadImpl(
      asset: asset,
      releaseId: releaseId,
      downloadUrl: downloadUrl,
      onProgress: onProgress,
      token: token,
    );
    _inFlight[asset.assetId] = future;
    return future.whenComplete(() {
      // 身份复核后再摘除：同一 assetId 的新 attempt 可能已登记自己的
      // future/令牌，无条件 remove 会把新 attempt 的登记一起抹掉。
      if (identical(_inFlight[asset.assetId], future)) {
        _inFlight.remove(asset.assetId);
      }
    });
  }

  Future<File> _downloadImpl({
    required OtaFirmwareAsset asset,
    required String releaseId,
    required String downloadUrl,
    void Function(int received, int total)? onProgress,
    required CancelToken token,
  }) async {
    try {
      final dir = await _resolveDir();
      final baseName = _safeFileName(asset.fileName);
      final partFile = File(_joinPath(dir.path, '$baseName.part'));
      final finalFile = File(_joinPath(dir.path, baseName));
      final sidecar = File(_joinPath(dir.path, '$baseName.part.json'));
      // 续传身份不合法（含 206 头校验失败、If-Range 失配）作废重下，
      // 但最多一次，防止与服务器状态反复拉锯。
      var restartUsed = false;
      // RC3-05：作废 partial 的删除失败不得吞掉，但主错误优先——删除
      // 失败以备注形式串入随后抛出的异常消息（cleanupNote），调用方
      // 与用户都能看到残留事实；不带主错误继续执行的作废点则让
      // _deletePartial 直接抛 CLEANUP_FAILED（fail closed，不带着
      // 失效状态继续写盘）。
      var cleanupNote = '';
      Future<void> invalidatePartial() async {
        // 归属已转移（RC3-04/05）：上层已开始新一轮下载同一资产，同名
        // `.part`/sidecar 属于新 attempt，按路径删除会毁掉它刚写的字节。
        // 与 [_deleteAssetPartials] 同一判定，只是删除点不同。
        if (!_ownsAsset()) {
          cleanupNote = '；partial 归属已转移，已跳过清理';
          return;
        }
        try {
          await _deletePartial(partFile, sidecar);
        } catch (e) {
          cleanupNote = '；partial 清理失败: $e';
        }
      }

      /// 取消检查的统一点（RC3-02）：已取消则按 keepPartial 语义处置
      /// 字节并抛 CANCELLED。登记令牌与发起请求之间、以及每轮续传的
      /// 读盘动作之间都有 await，取消可能落在其中任意一处；少了这些
      /// 检查点，取消会被静默吞掉或推迟到整包下完之后才生效。
      ///
      /// 归属转移（RC3-04/05）与取消同处：本 attempt 已不是该资产文件的
      /// owner 时，继续写盘/删文件都会破坏新 attempt 的状态，一律退出。
      Future<void> abortIfCancelled() async {
        if (!token.isCancelled && _ownsAsset()) return;
        if (!_cancelKeepsPartial) {
          await invalidatePartial();
        }
        throw OtaDownloadException(
            token.isCancelled ? '下载已取消$cleanupNote' : '下载归属已转移$cleanupNote',
            code: 'CANCELLED');
      }

      await abortIfCancelled();
      await cleanExpiredPartials(dir);
      await abortIfCancelled();
      while (true) {
        var sidecarData = await _readSidecar(sidecar);
        var localPartSize = await _fileLength(partFile);
        await abortIfCancelled();

        if (sidecarData != null &&
            !_sidecarMatches(sidecarData, asset, releaseId)) {
          // 身份漂移：作废旧 partial，从零开始。
          await _deletePartial(partFile, sidecar);
          sidecarData = null;
          localPartSize = 0;
        }

        if (localPartSize == asset.sizeBytes) {
          // 合同：不发 Range，先整文件校验，通过后原子转完成。
          if (await verifyFileMatchesAsset(partFile, asset)) {
            // RC3-05：整文件校验耗时期间用户可能已取消——rename 前核对
            // 令牌与归属，已取消/已易主一律按取消路径处置，不得把字节
            // 转成本 attempt 的完成包。
            await abortIfCancelled();
            await partFile.rename(finalFile.path);
            // RC3-05⑤：rename 是耗时 await，完成后需复核取消——取消若
            // 在复核前一刻到达，已落成的 finalFile 不得伪装成功返回。
            // keepPartial 语义下保留 finalFile（字节已验证正确，下次
            // 直接复用）。
            if (token.isCancelled || !_ownsAsset()) {
              if (!_cancelKeepsPartial) {
                await _deleteIfOwned(finalFile, sidecar);
              }
              throw OtaDownloadException(
                  token.isCancelled
                      ? '下载已取消$cleanupNote'
                      : '下载归属已转移$cleanupNote',
                  code: 'CANCELLED');
            }
            await _quietDelete(sidecar);
            return finalFile;
          }
          // 本地字节损坏不可续传（合同 :274）：删除并重新 latest
          // （旧 URL 对应字节与清单不符，不得沿旧 URL 重下，RC2-11）。
          await invalidatePartial();
          throw OtaDownloadException(
              '本地 partial 损坏（长度已满但 SHA 不符），需重新获取清单'
              '$cleanupNote',
              code: 'LOCAL_CORRUPT');
        } else if (localPartSize > asset.sizeBytes) {
          // 合同 :275：立即删除旧 partial 并重新 latest。
          await invalidatePartial();
          throw OtaDownloadException(
              '本地 partial 超长（$localPartSize > ${asset.sizeBytes}），'
              '需重新获取清单$cleanupNote', code: 'LOCAL_CORRUPT');
        }

        // ---- 发请求（续传时带 Range/If-Range）----
        // 分发前的最后一道取消检查（RC3-02）：此处之后就是真实网络请求，
        // 取消若正好落在上面的读盘 await 之间，必须在这里拦住，不得发出。
        await abortIfCancelled();
        final headers = <String, dynamic>{};
        var resumed = false;
        if (localPartSize > 0 && sidecarData != null) {
          // RC3-11：续传身份必须携带合法强 ETag（If-Range）——缺强 ETag
          // 的盲续传无法证明服务器字节未变，不得跳过续传身份约束：
          // 作废旧 partial 从零开始。
          final etag = sidecarData.strongEtag;
          if (etag == null || !_isStrongEtag(etag)) {
            await _deletePartial(partFile, sidecar);
            sidecarData = null;
            localPartSize = 0;
          } else {
            headers['Range'] = 'bytes=$localPartSize-';
            headers['If-Range'] = etag;
            resumed = true;
          }
        }
        // RC3-11⑤：每次尝试持有独立的 attempt token。会话 token 表示
        // 「用户取消整个下载」，而中止**本次响应**是另一回事：Dio 5.9.0
        // 的 handleResponseStream 不把包装流的 onCancel 传回底层 source，
        // 只 break 排空并不关闭上游连接，必须 cancel token 才真正中止。
        // 若用会话 token 去关旧响应，紧接着的重下请求会立即 CANCELLED，
        // 把服务器协议违规误报成用户取消；分离后旧响应可确定性关闭，
        // 新尝试拿到干净 token。会话取消向下级联，用户取消照常生效。
        final attemptToken = CancelToken();
        unawaited(token.whenCancel.then((_) {
          if (!attemptToken.isCancelled) attemptToken.cancel();
        }));
        Response<ResponseBody> response;
        try {
          response = await _dio.get<ResponseBody>(
            downloadUrl,
            options: Options(
              headers: headers,
              responseType: ResponseType.stream,
              // RC2-09：受控放行需要分类处理的 4xx（401/409/410/416），
              // 其余非 2xx 仍按 Dio 默认语义抛 badResponse。
              validateStatus: (status) => status != null &&
                  ((status >= 200 && status < 300) ||
                      status == 401 ||
                      status == 409 ||
                      status == 410 ||
                      status == 416),
            ),
            cancelToken: attemptToken,
          );
        } on DioException catch (e) {
          if (CancelToken.isCancel(e)) {
            // 用户取消（RC2-04）：默认删除 partial/sidecar；用户选择
            // 保留已下载部分时仅停止请求，字节留待下次续传。
            if (!_cancelKeepsPartial) {
              await invalidatePartial();
            }
            throw OtaDownloadException('下载已取消$cleanupNote',
                code: 'CANCELLED');
          }
          if (e.type == DioExceptionType.badResponse && e.response != null) {
            // RC3-10：非受控放行的 HTTP 状态（400/403/404/426/5xx…）
            // 统一归 OtaDownloadException 语义：可解析错误体携带
            // OtaHttpError，空/坏体携带裸 httpStatus——上层按同一规则
            // fail closed（稳定 4xx 闭锁），不经 generic 路径洗成普通
            // 网络失败。
            final status = e.response!.statusCode ?? 0;
            final data = e.response!.data;
            final errorBody = await _readErrorBody(
                data is ResponseBody ? data : null,
                cancelToken: attemptToken);
            throw OtaDownloadException(
                '下载返回 HTTP $status（errorCode: ${_errorCodeOf(errorBody)}）',
                code: 'HTTP_STATUS',
                httpStatus: status,
                httpError: _tryHttpError(errorBody, status,
                    requestIdHeader: _firstHeader(
                        e.response!.headers, 'x-request-id')));
          }
          rethrow;
        }
        final status = response.statusCode ?? 0;
        if (status == 416) {
          // XC-RANGE-AT-END：删除 partial 并要求上层重新 latest。
          await _drainBody(response.data, cancelToken: attemptToken);
          await invalidatePartial();
          throw OtaDownloadException(
              '区间已在文件末尾（416），需重新获取清单$cleanupNote',
              code: 'RANGE_AT_END');
        }
        if (status == 401) {
          // OTA-XC-HTTP-ERROR：TOKEN_INVALID/TOKEN_EXPIRED 是签名 URL
          // 授权过期（URL_EXPIRED，重新 latest）；本地 partial 字节仍对
          // 应该资产，保留供重新签发后续传。未知 errorCode fail closed
          // （RC3-10③：错误体解析为 OtaHttpError 供上层闭锁并携带
          // requestId，不静默降级为可重试失败）。
          final errorBody =
              await _readErrorBody(response.data, cancelToken: attemptToken);
          final errorCode = _errorCodeOf(errorBody);
          if (errorCode == 'TOKEN_INVALID' || errorCode == 'TOKEN_EXPIRED') {
            throw OtaDownloadException(
                '下载 URL 授权失效（HTTP 401 $errorCode），需重新获取清单',
                code: 'URL_EXPIRED');
          }
          throw OtaDownloadException(
              '下载返回 HTTP 401（errorCode: $errorCode）',
              code: 'HTTP_STATUS',
              httpStatus: status,
              httpError: _tryHttpError(errorBody, status,
                  requestIdHeader:
                      _firstHeader(response.headers, 'x-request-id')));
        }
        if (status == 410) {
          // XC-ASSET-DISABLED：资产下架，本地 metadata 一并作废。
          // RC3-10③：看码分流——body 明确 ASSET_DISABLED 才走下架路径，
          // 其他/未知 errorCode fail closed 归 HTTP_STATUS 附 OtaHttpError。
          final errorBody =
              await _readErrorBody(response.data, cancelToken: attemptToken);
          if (_errorCodeOf(errorBody) == 'ASSET_DISABLED') {
            await invalidatePartial();
            throw OtaDownloadException(
                '资产已下架（HTTP 410 ASSET_DISABLED），需重新获取清单'
                '$cleanupNote',
                code: 'URL_EXPIRED');
          }
          throw OtaDownloadException(
              '下载返回 HTTP 410（errorCode: ${_errorCodeOf(errorBody)}）',
              code: 'HTTP_STATUS',
              httpStatus: status,
              httpError: _tryHttpError(errorBody, status,
                  requestIdHeader:
                      _firstHeader(response.headers, 'x-request-id')));
        }
        if (status == 409) {
          // XC-ASSET-ARCHIVED：服务端状态冲突，需重新 latest；资产字节
          // 未变，本地 partial 保留（新清单身份不同时会自然作废）。
          // RC3-10③：看码分流——body 明确 ASSET_ARCHIVED 才走冲突刷新
          // 路径；其他/未知 errorCode fail closed 归 HTTP_STATUS。
          final errorBody =
              await _readErrorBody(response.data, cancelToken: attemptToken);
          if (_errorCodeOf(errorBody) == 'ASSET_ARCHIVED') {
            throw OtaDownloadException(
                '资产状态冲突（HTTP 409 ASSET_ARCHIVED），需重新获取清单',
                code: 'ASSET_CONFLICT');
          }
          throw OtaDownloadException(
              '下载返回 HTTP 409（errorCode: ${_errorCodeOf(errorBody)}）',
              code: 'HTTP_STATUS',
              httpStatus: status,
              httpError: _tryHttpError(errorBody, status,
                  requestIdHeader:
                      _firstHeader(response.headers, 'x-request-id')));
        }
        if (status != 200 && status != 206) {
          await _drainBody(response.data, cancelToken: attemptToken);
          throw OtaDownloadException('下载返回非法状态码: $status',
              code: 'HTTP_STATUS', httpStatus: status);
        }

        // ---- 响应头校验（写盘前完成，PR13）----
        final contentLengthHeader =
            int.tryParse(_firstHeader(response.headers, 'content-length') ?? '');
        final etagHeader = _firstHeader(response.headers, 'etag');
        final strongEtag =
            (etagHeader != null && _isStrongEtag(etagHeader)) ? etagHeader : null;
        if (resumed && status == 200) {
          // If-Range 不匹配（或服务器忽略 Range）：先截断旧 partial，禁止追加。
          await _truncateFile(partFile);
          localPartSize = 0;
          resumed = false;
        }
        // RC2-10：期望剩余量在响应模式归一（200 回退截断）之后统一计算，
        // 否则 200 回退后仍按旧剩余量校验导致整包下完也 LENGTH_MISMATCH。
        final expectedRemaining = asset.sizeBytes - localPartSize;
        if (resumed && status == 206) {
          final violation = _checkResumeHeaders(
            response: response,
            expectedStart: localPartSize,
            sizeBytes: asset.sizeBytes,
            expectedRemaining: expectedRemaining,
            contentLengthHeader: contentLengthHeader,
            ifRangeSent: headers.containsKey('If-Range'),
            expectedEtag: sidecarData?.strongEtag,
            responseEtag: strongEtag,
          );
          if (violation != null) {
            // 头校验失败即不进入写盘：先 drain 释放连接（RC3-11），
            // 再作废本地续传状态。
            // RC3-11⑤：drain 用 attempt token——排空只是本端读完，Dio
            // 5.9.0 的包装流不会因 break 关闭底层 source，必须 cancel
            // 才真正中止旧响应。attempt token 只作用于本次响应，首次
            // 违规后 continue 重下会新建 token，不会把协议违规误报成
            // 用户取消（旧实现为规避这一点，首次违规干脆不取消，旧连接
            // 因此挂到 GC/超时）。
            await _drainBody(response.data, cancelToken: attemptToken);
            await invalidatePartial();
            if (restartUsed) {
              throw OtaDownloadException(
                  '续传响应头校验反复失败: $violation$cleanupNote',
                  code: 'RESUME_PROTOCOL');
            }
            restartUsed = true;
            continue; // 从零重下
          }
        } else if (!resumed && status == 206) {
          // 未请求区间却返回 206：服务器协议违规，无法核对区间归属，
          // 作废本地状态 fail closed（不进入写盘）。
          await _drainBody(response.data, cancelToken: attemptToken);
          await invalidatePartial();
          throw OtaDownloadException('未请求区间却返回 206$cleanupNote',
              code: 'RESUME_PROTOCOL');
        } else {
          // 全新 200：Content-Length 必须等于 sizeBytes（缺失时由最终
          // 长度+SHA 校验兜底，不在此假绿）。
          if (contentLengthHeader != null &&
              contentLengthHeader != asset.sizeBytes) {
            await _drainBody(response.data, cancelToken: attemptToken);
            throw OtaDownloadException(
                '200 响应 Content-Length 与清单不符: '
                '$contentLengthHeader != ${asset.sizeBytes}',
                code: 'RESUME_PROTOCOL');
          }
        }
        // ETag 只记录本次响应的强 ETag；200 无/弱 ETag 时不得沿用旧值。
        await _writeSidecar(
          sidecar,
          asset: asset,
          releaseId: releaseId,
          etag: strongEtag,
        );

        // ---- 流式写盘 + Content-Digest 交叉核对 ----
        final contentDigest =
            await _parseContentDigest(response, cancelToken: attemptToken);
        final digestAccumulator = <Digest>[];
        final digestSink = contentDigest == null
            ? null
            : sha256.startChunkedConversion(
                ChunkedConversionSink<Digest>.withCallback(
                    (digests) => digestAccumulator.addAll(digests)),
              );
        var received = 0;
        final sink = partFile.openWrite(
          mode: resumed ? FileMode.append : FileMode.write,
        );
        // RC3-11⑤：Dio 5.9.0 的接收空闲计时器只在收到首个 data 事件后
        // 启动——响应头已到而首块正文永不到（或块间长停）时，await for
        // 无限挂起且 Dio 超时不触发。对包装流套 Stream.timeout 补偿：
        // 事件间隔超过 Dio receiveTimeout（默认 60s）即向流注入
        // TimeoutException，按网络中断类失败处置（partial 保留供续传）。
        final receiveIdleTimeout =
            _dio.options.receiveTimeout ?? const Duration(seconds: 60);
        try {
          await for (final chunk
              in response.data!.stream.timeout(receiveIdleTimeout)) {
            sink.add(chunk);
            digestSink?.add(chunk);
            received += chunk.length;
            onProgress?.call(localPartSize + received, asset.sizeBytes);
          }
          await sink.flush();
        } catch (e) {
          // RC3-11：Dio 5.9.0 的包装流 onCancel 不回传底层 source，
          // Stream.timeout / Dio receiveTimer 都只退出本端等待——读流
          // 异常（含停滞超时）时底层连接仍挂着。主动 cancel attempt
          // token 让 Dio 层中止底层请求（真实 adapter abort 连接），再
          // 原样上抛交上层按网络中断分类。attempt token 只覆盖本次响应，
          // 不污染后续尝试；与用户取消并发时 token 幂等，无副作用。
          if (e is TimeoutException ||
              (e is DioException &&
                  e.type == DioExceptionType.receiveTimeout)) {
            attemptToken.cancel();
          }
          rethrow;
        } finally {
          await sink.close();
          digestSink?.close();
        }
        if (received != expectedRemaining) {
          // 网络中断：保留 partial 供下次续传，不抛假成功。
          throw OtaDownloadException(
              '下载数据量不符: 期望 $expectedRemaining，实收 $received',
              code: 'LENGTH_MISMATCH');
        }
        if (contentDigest != null) {
          final actual = digestAccumulator.isEmpty
              ? null
              : digestAccumulator.first.toString();
          if (actual != contentDigest) {
            await invalidatePartial();
            throw OtaDownloadException(
                'Content-Digest 与实收字节不符: $actual != $contentDigest'
                '$cleanupNote',
                code: 'DIGEST_MISMATCH');
          }
        }
        if (!await verifyFileMatchesAsset(partFile, asset)) {
          await invalidatePartial();
          throw OtaDownloadException(
              '下载完成后 SHA-256 校验失败: ${asset.sha256}$cleanupNote',
              code: 'SHA_MISMATCH');
        }
        // RC3-05：verify 耗时期间用户可能已取消——字节已校验正确，
        // partial 按 keepPartial 语义处置，不得转成完成包。
        await abortIfCancelled();
        await partFile.rename(finalFile.path);
        // RC3-05⑤：rename 后复核取消/归属——verify 通过到 rename 返回之间
        // 取消或易主时，已完成包不得伪装成功；keepPartial 语义下保留
        // finalFile（字节已验证正确，下次直接复用）。
        if (token.isCancelled || !_ownsAsset()) {
          if (!_cancelKeepsPartial) {
            await _deleteIfOwned(finalFile, sidecar);
          }
          throw OtaDownloadException(
              token.isCancelled
                  ? '下载已取消$cleanupNote'
                  : '下载归属已转移$cleanupNote',
              code: 'CANCELLED');
        }
        await _quietDelete(sidecar);
        return finalFile;
      }
    } finally {
      // RC3-02：令牌在 download() 里与在途 future 同一同步段登记，摘除
      // 只有这一处——本体所有退出路径（含 _resolveDir 抛错）都经过 finally。
      // 按身份复核，避免抹掉同 assetId 新 attempt 已登记的令牌。
      if (identical(_cancelTokens[asset.assetId], token)) {
        _cancelTokens.remove(asset.assetId);
      }
    }
  }

  /// 校验本地文件当前字节仍与资产身份（长度+SHA-256）一致（PR12：
  /// BEGIN 前复核已下载包，防清单变化/文件被改后仍发送旧字节）。
  static Future<bool> verifyFileMatchesAsset(
      File file, OtaFirmwareAsset asset) async {
    if (!await file.exists()) return false;
    final length = await file.length();
    if (length != asset.sizeBytes) return false;
    final digest = await sha256.bind(file.openRead()).first;
    return digest.toString() == asset.sha256;
  }

  /// 用户显式取消：停止在途请求并删除对应 `.part` 与 sidecar。
  ///
  /// [keepPartial] 为 true 时仅停止在途请求，已下载字节保留供下次
  /// 续传（RC2-04：取消对话框「保留已下载部分」选项）。
  ///
  /// RC3-05：先有界等待在途 download 退出（sink 已关闭、不再写盘）
  /// 再删除 partial，避免删除与追加写并发。等待上限 5s；超时说明
  /// 在途路径未退出（sink 可能仍持有 partial 写句柄），此时**不删**——
  /// 删除既可能失败也不证明清理完成，留给 download() 自身的取消路径
  /// （token 已 cancel，其退出时会按 keepPartial 删除）与
  /// cleanExpiredPartials 的 24h 兜底（RC3-05⑤）。
  ///
  /// RC3-05⑥：无在途 download 时不存在并发写盘方，既有 partial/sidecar
  /// 必须照常删除。把"没有在途"与"等待超时"混为一谈会让取消一个已结束
  /// 的下载变成静默 no-op：用户看到取消成功，字节却留到 24h 兜底才清。
  ///
  /// RC3-05⑤：等待超时不再直接放弃——登记 [pendingCancelCleanup]，等
  /// 在途真正退出后按同一归属判定删除，由上层在 owner 退出后 await 收口。
  Future<void> cancel(String assetId, {bool keepPartial = false}) async {
    _cancelKeepsPartial = keepPartial;
    final token = _cancelTokens[assetId];
    token?.cancel();
    final inFlight = _inFlight[assetId];
    var settled = inFlight == null;
    if (inFlight != null) {
      try {
        await inFlight.timeout(cancelSettleTimeout);
        settled = true;
      } on TimeoutException {
        settled = false;
      } catch (_) {
        // 在途路径以异常退出同样代表已退出（sink 由其 finally 关闭）；
        // 异常本身由 download() 调用方收悉，此处不重复处置。
        settled = true;
      }
    }
    // 摘除按身份复核（RC3-02）：等待期间同一 assetId 的新 attempt 可能
    // 已登记自己的令牌，无条件 remove 会剥掉它后续被取消的能力。
    if (token != null && identical(_cancelTokens[assetId], token)) {
      _cancelTokens.remove(assetId);
    }
    if (keepPartial) return;
    if (settled) {
      await _deleteAssetPartials(assetId);
      return;
    }
    _deferredCleanup = _settleThenDelete(assetId, inFlight!);
  }

  /// 取消时在途未在上限内退出而登记的延后清理（RC3-05⑤）；无则为 null。
  Future<void>? get pendingCancelCleanup => _deferredCleanup;

  /// 等指定在途 download 完全退出后再删除该资产的 partial（RC3-05⑤）。
  Future<void> _settleThenDelete(String assetId, Future<File> inFlight) async {
    try {
      await inFlight;
    } catch (_) {
      // 以异常退出同样代表已退出（sink 已关闭）；异常由 download()
      // 调用方收悉，此处只负责退出后清理。
    }
    await _deleteAssetPartials(assetId);
  }

  /// 按 assetId 删除该资产的 `.part` 与 sidecar。
  ///
  /// 归属判定 [stillOwns] 在每个**删除边界**上复核（RC3-04/05）：本函数
  /// 全程有 await，取消后用户可能立刻重新下载同一资产，新 attempt 会写出
  /// 同名 `.part`/sidecar——按 assetId 匹配挡不住（两次 attempt 的 assetId
  /// 本来就相同），迟到的枚举会把新 attempt 刚写的字节删掉。
  Future<void> _deleteAssetPartials(String assetId) async {
    if (!_ownsAsset()) return;
    final dir = await _resolveDir();
    await for (final entity in dir.list()) {
      if (entity is! File) continue;
      final name = entity.uri.pathSegments.last;
      if (!name.endsWith('.part')) continue;
      final sidecar = File('${entity.path}.json');
      final data = await _readSidecar(sidecar);
      if (data == null || data.assetId != assetId) continue;
      // 删除边界上的最后复核：枚举与本行之间隔着读 sidecar 的 await。
      if (!_ownsAsset()) return;
      await _deletePartial(entity, sidecar);
    }
  }

  /// 本 downloader 是否仍拥有该资产文件（无判定函数时视为拥有）。
  bool _ownsAsset() => stillOwns?.call() ?? true;

  /// 归属仍在时才按路径删除（RC3-04/05）。
  ///
  /// 删除点分布在多个 await 之后，归属可能在这些窗口内转移给新 attempt：
  /// 两次 attempt 的 assetId 与文件名本来就相同，按路径删除会毁掉新
  /// attempt 刚写下的字节。判定必须在**删除边界**上做。
  Future<void> _deleteIfOwned(File file, File sidecar) async {
    if (!_ownsAsset()) return;
    await _deletePartial(file, sidecar);
  }

  /// 清理超过 24 小时的 `.part` 与 sidecar（按 sidecar 更新时间判定，
  /// 无 sidecar 的孤儿 partial、无 partial 的孤儿 sidecar/tmp 一并删除）。
  Future<void> cleanExpiredPartials(Directory dir) async {
    final cutoff = DateTime.now()
        .subtract(const Duration(hours: 24))
        .millisecondsSinceEpoch;
    final partFiles = <String>{};
    await for (final entity in dir.list()) {
      if (entity is! File) continue;
      if (!entity.path.endsWith('.part')) continue;
      partFiles.add(entity.path);
      final sidecar = File('${entity.path}.json');
      final data = await _readSidecar(sidecar);
      final updatedAt = data?.updatedAtMs;
      if (updatedAt == null || updatedAt <= cutoff) {
        await _deletePartial(entity, sidecar);
      }
    }
    // 孤儿 sidecar（对应 .part 已不存在）与 sidecar 临时文件。
    await for (final entity in dir.list()) {
      if (entity is! File) continue;
      if (!entity.path.endsWith('.part.json') &&
          !entity.path.endsWith('.part.json.tmp')) {
        continue;
      }
      if (entity.path.endsWith('.tmp')) {
        await _quietDelete(entity);
        continue;
      }
      final counterPart = entity.path.substring(0, entity.path.length - 5);
      if (!partFiles.contains(counterPart) && !await File(counterPart).exists()) {
        await _quietDelete(entity);
      }
    }
  }

  // ---- 内部 ----

  /// 206 响应头校验集（OTA-XC-HTTP-RESUME）。返回 null 表示通过，
  /// 否则返回首个违规描述（调用方作废 partial 从零重下）。
  String? _checkResumeHeaders({
    required Response<ResponseBody> response,
    required int expectedStart,
    required int sizeBytes,
    required int expectedRemaining,
    required int? contentLengthHeader,
    required bool ifRangeSent,
    required String? expectedEtag,
    required String? responseEtag,
  }) {
    final acceptRanges = _firstHeader(response.headers, 'accept-ranges');
    if (acceptRanges == null || acceptRanges.trim().toLowerCase() != 'bytes') {
      return '206 缺 Accept-Ranges: bytes';
    }
    final contentRange = _firstHeader(response.headers, 'content-range');
    final match =
        RegExp(r'^bytes (\d+)-(\d+)/(\d+)$').firstMatch(contentRange ?? '');
    if (match == null) {
      return '206 Content-Range 非法: $contentRange';
    }
    final start = int.parse(match.group(1)!);
    final end = int.parse(match.group(2)!);
    final total = int.parse(match.group(3)!);
    if (start != expectedStart ||
        end != sizeBytes - 1 ||
        total != sizeBytes) {
      return '206 Content-Range 区间不符: $contentRange';
    }
    if (contentLengthHeader == null ||
        contentLengthHeader != expectedRemaining) {
      return '206 Content-Length 不符: $contentLengthHeader != $expectedRemaining';
    }
    if (ifRangeSent && (responseEtag == null || responseEtag != expectedEtag)) {
      return '206 ETag 与 If-Range 不一致（响应无强 ETag 或漂移）';
    }
    return null;
  }

  /// 解析 Content-Digest（RFC 9530）中的 sha-256 项（hex 小写）。
  ///
  /// 无该 header 时返回 null（服务器未提供交叉核对，由最终长度+SHA
  /// 校验兜底）；header 存在时按 RFC 9530 严格判定（RC3-11）：
  /// - sha-256 项必须唯一（多项歧义 fail closed）；
  /// - 摘要必须为规范 base64：32 字节恰编码为 43 数据字符 + 1 个
  ///   padding `=`（非规范 padding/长度一律 fail closed）；
  /// - header 声明了 digest 却不含 sha-256 项（如只有 sha-512）：
  ///   声明了校验却无法核对，同样 fail closed。
  /// 不得把"声称有校验却无法核对"的响应静默降级为无校验。
  ///
  /// fail closed 路径走 [_drainBody] 有界消费并主动取消 [cancelToken]
  /// （RC3-11⑤：包装流的取消到不了 Dio 底层 source）。
  Future<String?> _parseContentDigest(Response<ResponseBody> response,
      {CancelToken? cancelToken}) async {
    final raw = _firstHeader(response.headers, 'content-digest');
    if (raw == null) return null;
    final items =
        raw.split(',').map((e) => e.trim()).where((e) => e.isNotEmpty);
    final sha256Items = items.where((e) => e.startsWith('sha-256=')).toList();
    if (sha256Items.isEmpty) {
      await _drainBody(response.data, cancelToken: cancelToken);
      throw OtaDownloadException(
          'Content-Digest 不含 sha-256 项: $raw', code: 'RESUME_PROTOCOL');
    }
    if (sha256Items.length > 1) {
      await _drainBody(response.data, cancelToken: cancelToken);
      throw OtaDownloadException(
          'Content-Digest 含多个 sha-256 项: $raw', code: 'RESUME_PROTOCOL');
    }
    final match =
        RegExp(r'^sha-256=:([A-Za-z0-9+/]{43}=):$').firstMatch(sha256Items.single);
    if (match == null) {
      await _drainBody(response.data, cancelToken: cancelToken);
      throw OtaDownloadException(
          'Content-Digest sha-256 项非规范 base64（须 43 数据字符 + '
          '单 padding）: $raw', code: 'RESUME_PROTOCOL');
    }
    // 正则已保证字符集与长度，base64 解码必为 32 字节。
    final bytes = base64.decode(match.group(1)!);
    return bytes.map((b) => b.toRadixString(16).padLeft(2, '0')).join();
  }

  Future<Directory> _resolveDir() async {
    final provider = dirProvider;
    if (provider != null) {
      return provider();
    }
    throw OtaDownloadException('未配置下载目录提供器 dirProvider',
        code: 'NO_DIR');
  }

  /// 响应体事件间隔上限（零事件停滞保护）。
  ///
  /// RC3-11⑥：Dio 5.9.0 的接收空闲计时器只在收到首个 data 事件后启动
  /// （`handleResponseStream` 里 `watchReceiveTimeout` 挂在 data 回调），
  /// 响应头已到而正文一个事件都不来时不会触发。主体写盘路径已套
  /// `Stream.timeout` 补偿，drain / 错误体读取同样需要——否则一个只发头
  /// 不发体的服务端能让 401/409/410/416 分流和头校验失败路径永久挂起，
  /// 且这些路径都在 `await` 上，连取消都到不了。
  Duration get _bodyIdleTimeout =>
      _dio.options.receiveTimeout ?? const Duration(seconds: 60);

  /// 给响应体流加空闲超时：停滞即取消上游（包装流的取消到不了 Dio
  /// 底层 source，必须 cancel token）并向本端注入 [TimeoutException]，
  /// 由调用方按“坏体”fail closed 处置，不做半截正文解析。
  Stream<List<int>> _guardBodyIdle(
      Stream<List<int>> stream, CancelToken? cancelToken) {
    return stream.timeout(_bodyIdleTimeout, onTimeout: (sink) {
      if (cancelToken != null && !cancelToken.isCancelled) {
        cancelToken.cancel();
      }
      sink.addError(
          TimeoutException('响应体停滞超时', _bodyIdleTimeout), StackTrace.current);
      sink.close();
    });
  }

  /// 消费并丢弃响应体流（释放连接；正文不参与判定的路径用）。
  ///
  /// RC3-11：有界消费——读满 [maxBytes] 即 break 取消订阅，禁止对
  /// 任意响应无界 drain（恶意/超大响应不得占用无界内存与时间）。
  ///
  /// RC3-11⑤：break 只取消 Dio 的包装流——锁定的 Dio 5.9.0
  /// handleResponseStream 不把包装流的 onCancel 传回底层 source，
  /// 原始响应仍可能被继续读取。达界后主动 cancel [cancelToken]，
  /// 让 Dio 层中止底层请求（token 与本次尝试绑定，无跨尝试复用）。
  Future<void> _drainBody(ResponseBody? body,
      {int maxBytes = 64 * 1024, CancelToken? cancelToken}) async {
    final stream = body?.stream;
    if (stream == null) return;
    try {
      var received = 0;
      await for (final chunk in _guardBodyIdle(stream, cancelToken)) {
        received += chunk.length;
        if (received >= maxBytes) {
          cancelToken?.cancel();
          break;
        }
      }
    } catch (_) {
      // 排空失败（含停滞超时）不掩盖主错误；上游已在 onTimeout 中止。
    }
  }

  /// 读取错误响应体并解析为 JSON 对象（401/409/410 看码分流需要，
  /// RC3-10③）。
  ///
  /// RC3-11：有界读取——错误体应是小型 JSON，超过 [maxBytes] 视为
  /// 坏体返回 null（上层按裸状态码 fail closed），并取消流释放连接；
  /// 正文非法 JSON 或非对象时同样返回 null。
  ///
  /// RC3-11⑤：overflow break 后同样主动 cancel [cancelToken]（包装流
  /// 的取消到不了 Dio 底层 source，理由同 [_drainBody]）。
  /// RC3-11⑥：零事件停滞由 [_guardBodyIdle] 兜底，超时按坏体返回 null。
  Future<Map<String, dynamic>?> _readErrorBody(ResponseBody? body,
      {int maxBytes = 64 * 1024, CancelToken? cancelToken}) async {
    final stream = body?.stream;
    if (stream == null) return null;
    try {
      final bytes = <int>[];
      var overflow = false;
      await for (final chunk in _guardBodyIdle(stream, cancelToken)) {
        if (bytes.length + chunk.length > maxBytes) {
          overflow = true;
          cancelToken?.cancel();
          break;
        }
        bytes.addAll(chunk);
      }
      if (overflow) return null;
      final decoded = jsonDecode(utf8.decode(bytes));
      if (decoded is Map<String, dynamic>) return decoded;
      return null;
    } catch (_) {
      return null;
    }
  }

  String? _errorCodeOf(Map<String, dynamic>? body) {
    final code = body?['errorCode'];
    if (code is String && code.isNotEmpty) return code;
    return null;
  }

  /// 把错误体解析为 [OtaHttpError]（结构非法/缺 errorCode 时返回 null，
  /// 调用方按未知错误 fail closed）。供上层闭锁终止态并携带 requestId
  /// （RC3-10⑤：body 缺 requestId 时回填响应头 x-request-id，排查线索
  /// 不得在下载侧丢失）。
  OtaHttpError? _tryHttpError(Map<String, dynamic>? body, int status,
      {String? requestIdHeader}) {
    if (body == null) return null;
    try {
      return OtaHttpError.fromBody(body, status,
          requestIdHeader: requestIdHeader);
    } on OtaLatestParseException {
      return null;
    }
  }

  String _joinPath(String dir, String name) =>
      '$dir${Platform.pathSeparator}$name';

  Future<int> _fileLength(File file) async {
    if (!await file.exists()) return 0;
    return file.length();
  }

  Future<void> _truncateFile(File file) async {
    final raf = await file.open(mode: FileMode.write);
    try {
      await raf.truncate(0);
    } finally {
      await raf.close();
    }
  }

  Future<OtaSidecarData?> _readSidecar(File sidecar) async {
    if (!await sidecar.exists()) return null;
    try {
      final raw = await sidecar.readAsString();
      final map = jsonDecode(raw);
      if (map is! Map<String, dynamic>) return null;
      final assetId = map['assetId'];
      final releaseId = map['releaseId'];
      final sha = map['sha256'];
      final size = map['sizeBytes'];
      if (assetId is! String ||
          releaseId is! String ||
          sha is! String ||
          size is! int) {
        return null;
      }
      final rawEtag =
          map['strongEtag'] is String ? map['strongEtag'] as String : null;
      // RC3-11：sidecar 读出的强 ETag 同样按标准校验——内部未转义
      // 引号等非法形态不得进入 If-Range 续传身份（置 null 后续传
      // 前的强 ETag 检查会作废该 partial 从零开始）。
      final strongEtag =
          rawEtag != null && _isStrongEtag(rawEtag) ? rawEtag : null;
      return OtaSidecarData(
        assetId: assetId,
        releaseId: releaseId,
        sha256: sha,
        sizeBytes: size,
        strongEtag: strongEtag,
        updatedAtMs: map['updatedAtMs'] is int ? map['updatedAtMs'] as int : 0,
      );
    } catch (_) {
      // 损坏 sidecar 视为不存在（调用方从零开始）。
      return null;
    }
  }

  Future<void> _writeSidecar(
    File sidecar, {
    required OtaFirmwareAsset asset,
    required String releaseId,
    String? etag,
  }) async {
    final payload = jsonEncode({
      'assetId': asset.assetId,
      'releaseId': releaseId,
      'sha256': asset.sha256,
      'sizeBytes': asset.sizeBytes,
      'strongEtag': etag,
      'updatedAtMs': DateTime.now().millisecondsSinceEpoch,
    });
    // 原子写：先临时文件再 rename。
    final tmp = File('${sidecar.path}.tmp');
    await tmp.writeAsString(payload, flush: true);
    await tmp.rename(sidecar.path);
  }

  bool _sidecarMatches(
    OtaSidecarData data,
    OtaFirmwareAsset asset,
    String releaseId,
  ) {
    return data.assetId == asset.assetId &&
        data.releaseId == releaseId &&
        data.sha256 == asset.sha256 &&
        data.sizeBytes == asset.sizeBytes;
  }

  /// 失败清理路径的删除（RC3-05⑤）：删除失败必须抛出——「失败后清理」
  /// 不兑现却被吞掉时，调用方会误以为状态已复位（partial 残留、下次
  /// 续传基于脏状态），失败上报不兑现。主错误已在抛出途中的路径用
  /// [invalidatePartial] 把本异常串入 cleanupNote。
  Future<void> _deletePartial(File partFile, File sidecar) async {
    await _deleteStrict(partFile);
    await _deleteStrict(sidecar);
    final tmp = File('${sidecar.path}.tmp');
    await _deleteStrict(tmp);
  }

  Future<void> _deleteStrict(File file) async {
    if (await file.exists()) {
      try {
        await file.delete();
      } catch (e) {
        throw OtaDownloadException(
            '清理失败（${file.path}）: $e', code: 'CLEANUP_FAILED');
      }
    }
  }

  /// 宽松删除：仅用于成功路径的善后（finalFile 已验证落成，sidecar/tmp
  /// 残留不改变成功语义，cleanExpiredPartials 24h 兜底会再清）。失败
  /// 路径一律用 [_deletePartial]/[_deleteStrict]，禁止吞掉删除失败
  /// （RC3-05⑤）。
  Future<void> _quietDelete(File file) async {
    if (await file.exists()) {
      try {
        await file.delete();
      } catch (_) {
        // 成功路径善后：残留交给 24h 兜底清理。
      }
    }
  }

  String? _firstHeader(Headers headers, String name) {
    final values = headers.value(name);
    return values;
  }

  /// 强 ETag 判定（RC2-11/RC3-11）：RFC 7232 opaque-tag 形态——双引号
  /// 包裹的可见 ASCII；字符集为 0x21 与 0x23-0x7E（`[!#-~]`，**不含**
  /// 内部未转义双引号 0x22）；`W/` 弱验证、裸 token（无引号）、`"*"`
  /// 通配都不满足，不得作为 If-Range/续传身份；200 无强 ETag
  /// 不得沿用旧值。
  bool _isStrongEtag(String etag) =>
      etag != '"*"' && RegExp(r'^"[!#-~]+"$').hasMatch(etag);

  String _safeFileName(String name) {
    final sanitized = name.replaceAll(RegExp(r'[^A-Za-z0-9._-]'), '_');
    return sanitized.isEmpty ? 'firmware' : sanitized;
  }
}

/// sidecar 记录的资产身份。
class OtaSidecarData {
  OtaSidecarData({
    required this.assetId,
    required this.releaseId,
    required this.sha256,
    required this.sizeBytes,
    this.strongEtag,
    required this.updatedAtMs,
  });

  final String assetId;
  final String releaseId;
  final String sha256;
  final int sizeBytes;
  final String? strongEtag;
  final int updatedAtMs;
}

/// 下载失败的稳定领域异常（code 供上层分类处置）。
class OtaDownloadException implements Exception {
  OtaDownloadException(this.message,
      {this.code, this.httpError, this.httpStatus});

  final String message;

  /// `RANGE_AT_END`（416 → 重新 latest）/ `URL_EXPIRED`（401 TOKEN_*、
  /// 410 ASSET_DISABLED → 重新 latest）/ `ASSET_CONFLICT`（409
  /// ASSET_ARCHIVED → 重新 latest）/ `LOCAL_CORRUPT`（本地 partial
  /// 损坏/超长 → 重新 latest）/ `HTTP_STATUS` / `RESUME_PROTOCOL` /
  /// `LENGTH_MISMATCH` / `DIGEST_MISMATCH` / `SHA_MISMATCH` /
  /// `CANCELLED` / `NO_DIR` / `CLEANUP_FAILED`（partial 清理失败）。
  final String? code;

  /// HTTP_STATUS 时若错误体可解析则携带（RC3-10③）：上层据此把
  /// 终止型/未知 errorCode 闭锁为 terminalState 并携带 requestId。
  final OtaHttpError? httpError;

  /// HTTP 状态码（RC3-10）：受控（401/409/410）与非受控（400/403/
  /// 426/5xx…经 Dio badResponse 统一转换）HTTP 错误一律携带；错误体
  /// 不可解析（httpError == null）时上层按裸状态码 fail closed——
  /// 稳定 4xx 属服务端明确拒绝，闭锁入口。
  final int? httpStatus;

  @override
  String toString() => 'OtaDownloadException($code): $message';
}
