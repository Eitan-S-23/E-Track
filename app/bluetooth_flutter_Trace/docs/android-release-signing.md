# Android Release Signing

Release APKs must be signed with the same private key to support overwrite installation. If no fixed release key is configured, this project falls back to debug signing so CI can still run, but APKs from different CI runs may not update over each other.

## Generate a Release Key

Run from the repository root:

```powershell
pwsh ./scripts/generate-android-release-keystore.ps1
```

If `pwsh` is not available, use Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\generate-android-release-keystore.ps1
```

The script keeps the private key outside the repository by default and writes a GitHub Secrets file next to it. By default it creates:

- `$HOME/.ble-monitor-signing/ble-monitor-release.keystore`
- `$HOME/.ble-monitor-signing/github-secrets.txt`
- `android/key.properties`

The keystore and `android/key.properties` are local secrets and must not be committed. `android/key.properties` points Gradle to the generated keystore for local release signing when needed. To generate only the keystore and GitHub Secrets file, pass `-SkipLocalProperties`.

## Configure GitHub Actions Secrets

Add each line from `$HOME/.ble-monitor-signing/github-secrets.txt` as a repository secret:

- `ANDROID_RELEASE_KEYSTORE_BASE64`
- `ANDROID_RELEASE_KEYSTORE_PASSWORD`
- `ANDROID_RELEASE_KEY_ALIAS`
- `ANDROID_RELEASE_KEY_PASSWORD`

The workflow also accepts the same sideload secret names used by RikkaHub:

- `SIDELOAD_KEYSTORE_BASE64`
- `SIDELOAD_KEYSTORE_PASSWORD`
- `SIDELOAD_KEY_ALIAS`
- `SIDELOAD_KEY_PASSWORD`

Configure one complete set. If both sets are present, `ANDROID_RELEASE_*` takes precedence. After the secrets are configured, GitHub Actions restores the keystore during the Android job and signs release APKs with the fixed key. If no fixed signing secrets are configured, CI falls back to debug signing and APKs from different CI runs may not update each other.

## Updating Existing Installs

Android only allows overwrite installation when the installed APK and the new APK have the same signing certificate. If a device already has an APK signed with the previous debug or CI-generated key, uninstall it once after switching to the fixed release key. Later APKs signed with this same key can update normally.
