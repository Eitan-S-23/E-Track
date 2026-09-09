class ShareLinks {
  ShareLinks._();

  static const String appId = 'trace';
  static const String appName = 'Trace';
  static const String appPackageName = 'com.wen.gaia.gaia';
  static const String appSchemeUrl = 'trace://speedometer';
  static const String landingPageUrl = 'https://eitan-s-23.github.io/Trace/';
  static const String updateChannel = String.fromEnvironment(
    'TRACE_UPDATE_CHANNEL',
    defaultValue: 'stable',
  );
  static const String cloudflareUpdateManifestUrl = String.fromEnvironment(
    'TRACE_CLOUDFLARE_UPDATE_MANIFEST_URL',
    defaultValue: '',
  );
  static const String cloudflareFirmwareLatestUrl = String.fromEnvironment(
    'TRACE_CLOUDFLARE_FIRMWARE_LATEST_URL',
    defaultValue: '',
  );
  static const String emergencyUpdateManifestUrl = String.fromEnvironment(
    'TRACE_EMERGENCY_UPDATE_MANIFEST_URL',
    defaultValue: '',
  );
  static const String updatePayloadPublicKeyBase64 = String.fromEnvironment(
    'TRACE_UPDATE_PAYLOAD_ED25519_PUBLIC_KEY_BASE64',
    defaultValue: '',
  );
  static const String githubReleaseDownloadBaseUrl =
      'https://github.com/Eitan-S-23/Trace/releases/download/';
  static const String githubLatestReleaseDownloadBaseUrl =
      'https://github.com/Eitan-S-23/Trace/releases/latest/download/';
  static const String legacyGithubLatestManifestUrl =
      '${githubLatestReleaseDownloadBaseUrl}ble-monitor-update.json';
  static String get androidUpdateManifestUrl =>
      cloudflareUpdateManifestUrl.isNotEmpty
          ? cloudflareUpdateManifestUrl
          : legacyGithubLatestManifestUrl;
  static String get announcementsUrl {
    if (cloudflareUpdateManifestUrl.isEmpty) return '';
    final manifestUri = Uri.tryParse(cloudflareUpdateManifestUrl);
    if (manifestUri == null) return '';
    return manifestUri.replace(path: '/api/public/announcements').toString();
  }

  static String get firmwareLatestUrl {
    if (cloudflareFirmwareLatestUrl.isNotEmpty) {
      return cloudflareFirmwareLatestUrl;
    }
    if (cloudflareUpdateManifestUrl.isEmpty) return '';
    final manifestUri = Uri.tryParse(cloudflareUpdateManifestUrl);
    if (manifestUri == null) return '';
    return manifestUri.replace(path: '/api/public/firmware/latest').toString();
  }

  static bool get hasAnnouncementsEndpoint => announcementsUrl.isNotEmpty;

  static Uri announcementsUri({String? channel, int limit = 10}) {
    final endpoint = announcementsUrl;
    if (endpoint.isEmpty) {
      throw StateError('Cloudflare announcements URL is not configured');
    }
    final uri = Uri.parse(endpoint);
    final query = Map<String, String>.from(uri.queryParameters);
    query['appId'] = appId;
    query['platform'] = 'android';
    query['channel'] = channel ?? updateChannel;
    query['limit'] = limit.toString();
    return uri.replace(queryParameters: query);
  }

  static bool get hasFirmwareUpdateEndpoint => firmwareLatestUrl.isNotEmpty;

  /// latest query 参数对象（OTA-XC-CLOUD-QUERY-MAPPING）。
  ///
  /// 构造即校验：任何字段缺失/越界都抛 [ArgumentError]，禁止半参数请求。
  static Map<String, String> firmwareLatestQuery({
    required String deviceModel,
    required int currentVersionCode,
    required String currentImageSha,
    required int hardwareRevision,
    required int layoutId,
    required int bootVersion,
    required int protocolVersion,
    required int appVersionCode,
    String? channel,
  }) {
    if (deviceModel.isEmpty) {
      throw ArgumentError('deviceModel 不能为空');
    }
    if (currentVersionCode < 0) {
      throw ArgumentError('currentVersionCode 必须非负: $currentVersionCode');
    }
    final shaOk =
        currentImageSha.length == 64 && RegExp(r'^[0-9a-f]{64}$').hasMatch(currentImageSha);
    if (!shaOk) {
      throw ArgumentError('currentImageSha 必须为 64 位小写 hex');
    }
    if (hardwareRevision < 0) {
      throw ArgumentError('hardwareRevision 必须非负: $hardwareRevision');
    }
    if (layoutId < 0 || layoutId > 255) {
      throw ArgumentError('layoutId 必须在 0..255: $layoutId');
    }
    if (bootVersion < 0 || bootVersion > 255) {
      throw ArgumentError('bootVersion 必须在 0..255: $bootVersion');
    }
    if (protocolVersion < 0 || protocolVersion > 255) {
      throw ArgumentError('protocolVersion 必须在 0..255: $protocolVersion');
    }
    if (appVersionCode < 0 || appVersionCode > 2100000000) {
      throw ArgumentError(
          'appVersionCode 必须在 0..2100000000: $appVersionCode');
    }
    // channel 闭集合校验（OTA-XC-CLOUD-QUERY-MAPPING）：未知通道在
    // 发请求前失败，不允许半参数请求打到云端。
    final effectiveChannel = channel ?? updateChannel;
    if (effectiveChannel != 'stable' && effectiveChannel != 'beta') {
      throw ArgumentError('channel 必须是 stable 或 beta: $effectiveChannel');
    }
    return {
      'appId': appId,
      'deviceModel': deviceModel,
      'channel': effectiveChannel,
      'currentVersionCode': currentVersionCode.toString(),
      'currentImageSha': currentImageSha,
      'hardwareRevision': hardwareRevision.toString(),
      'layoutId': layoutId.toString(),
      'bootVersion': bootVersion.toString(),
      'protocolVersion': protocolVersion.toString(),
      'appVersionCode': appVersionCode.toString(),
    };
  }

  /// 最新固件 latest 查询 URI（typed 全参数，OTA-XC-CLOUD-QUERY-MAPPING）。
  ///
  /// 旧 `currentVersion` 字符串参数已删除：v2 query 不再接受页面字符串
  /// 版本参与选包。字段校验见 [firmwareLatestQuery]。
  static Uri firmwareLatestUri({
    required String deviceModel,
    required int currentVersionCode,
    required String currentImageSha,
    required int hardwareRevision,
    required int layoutId,
    required int bootVersion,
    required int protocolVersion,
    required int appVersionCode,
    String? channel,
  }) {
    final endpoint = firmwareLatestUrl;
    if (endpoint.isEmpty) {
      throw StateError('Cloudflare firmware latest URL is not configured');
    }
    final uri = Uri.parse(endpoint);
    final query = Map<String, String>.from(uri.queryParameters);
    query.addAll(firmwareLatestQuery(
      deviceModel: deviceModel,
      currentVersionCode: currentVersionCode,
      currentImageSha: currentImageSha,
      hardwareRevision: hardwareRevision,
      layoutId: layoutId,
      bootVersion: bootVersion,
      protocolVersion: protocolVersion,
      appVersionCode: appVersionCode,
      channel: channel,
    ));
    return uri.replace(queryParameters: query);
  }

  static const String androidApkUrl =
      '${githubLatestReleaseDownloadBaseUrl}ble-monitor-android.apk';
  static const String windowsDownloadUrl =
      '${githubLatestReleaseDownloadBaseUrl}ble-monitor-windows.zip';

  static final Uri landingPageUri = Uri.parse(landingPageUrl);

  static String githubReleaseAssetUrl(String releaseTag, String assetName) {
    return '$githubReleaseDownloadBaseUrl'
        '${Uri.encodeComponent(releaseTag)}/'
        '${Uri.encodeComponent(assetName)}';
  }
}
