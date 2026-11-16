/// An accepted device choice is scoped to one connection, image and package.
class OtaUpgradeConsent {
  const OtaUpgradeConsent({required this.address, required this.linkGeneration,
    required this.baseImageSha256, required this.versionCode,
    required this.packageSha256, required this.targetImageSha256, this.expiresAt});
  final String address, baseImageSha256, packageSha256, targetImageSha256;
  final int linkGeneration, versionCode;
  final DateTime? expiresAt;
  bool get expired => expiresAt != null && !DateTime.now().isBefore(expiresAt!);
}
