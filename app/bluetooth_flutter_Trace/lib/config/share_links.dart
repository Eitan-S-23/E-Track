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

  static Uri firmwareLatestUri({
    required String deviceModel,
    required String currentVersion,
    int? currentVersionCode,
    String? channel,
  }) {
    final endpoint = firmwareLatestUrl;
    if (endpoint.isEmpty) {
      throw StateError('Cloudflare firmware latest URL is not configured');
    }
    final uri = Uri.parse(endpoint);
    final query = Map<String, String>.from(uri.queryParameters);
    query['appId'] = appId;
    query['deviceModel'] = deviceModel;
    query['channel'] = channel ?? updateChannel;
    query['currentVersion'] = currentVersion;
    if (currentVersionCode != null) {
      query['currentVersionCode'] = currentVersionCode.toString();
    }
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
