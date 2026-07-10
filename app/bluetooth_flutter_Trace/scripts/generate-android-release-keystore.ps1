param(
    [string] $OutputDirectory = (Join-Path $HOME ".ble-monitor-signing"),
    [string] $Alias = "ble-monitor-release",
    [int] $ValidityDays = 10000,
    [string] $KeytoolPath,
    [string] $KeyPropertiesPath = (Join-Path $PSScriptRoot "..\android\key.properties"),
    [switch] $SkipLocalProperties,
    [switch] $Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function New-Password {
    param([int] $ByteCount = 32)

    $bytes = New-Object byte[] $ByteCount
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($bytes)
    } finally {
        $rng.Dispose()
    }
    return [Convert]::ToBase64String($bytes).TrimEnd("=").Replace("+", "-").Replace("/", "_")
}

function Get-KeytoolCandidates {
    $candidateRoots = @(
        $env:JAVA_HOME,
        $env:JDK_HOME,
        $env:ANDROID_STUDIO_JBR,
        "${env:ProgramFiles}\Android\Android Studio\jbr",
        "${env:ProgramFiles}\Android\Android Studio\jre",
        "${env:ProgramFiles}\Java",
        "${env:ProgramFiles}\Eclipse Adoptium",
        "${env:ProgramFiles}\Microsoft",
        "${env:ProgramFiles}\Zulu",
        "${env:ProgramFiles(x86)}\Java"
    ) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }

    $directCandidates = @()
    if (-not [string]::IsNullOrWhiteSpace($KeytoolPath)) {
        $directCandidates += $KeytoolPath
    }

    $pathCommand = Get-Command keytool -ErrorAction SilentlyContinue
    if ($null -ne $pathCommand) {
        $directCandidates += $pathCommand.Source
    }

    foreach ($candidate in $directCandidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            Get-Item -LiteralPath $candidate
        }
    }

    foreach ($root in $candidateRoots) {
        if (-not (Test-Path -LiteralPath $root)) {
            continue
        }

        $binKeytool = Join-Path $root "bin\keytool.exe"
        if (Test-Path -LiteralPath $binKeytool -PathType Leaf) {
            Get-Item -LiteralPath $binKeytool
        }

        Get-ChildItem -LiteralPath $root -Directory -ErrorAction SilentlyContinue |
            ForEach-Object {
                $nestedKeytool = Join-Path $_.FullName "bin\keytool.exe"
                if (Test-Path -LiteralPath $nestedKeytool -PathType Leaf) {
                    Get-Item -LiteralPath $nestedKeytool
                }
            }
    }
}

$keytool = Get-KeytoolCandidates |
    Select-Object -ExpandProperty FullName -Unique |
    Select-Object -First 1

if (-not $keytool) {
    throw @"
keytool was not found.

Install a JDK, then rerun this script. Recommended options:
  winget install EclipseAdoptium.Temurin.17.JDK
  winget install Microsoft.OpenJDK.17

If a JDK is already installed, either set JAVA_HOME or pass keytool explicitly:
  `$env:JAVA_HOME = "C:\Program Files\Eclipse Adoptium\jdk-17.x.x"
  .\scripts\generate-android-release-keystore.ps1

  .\scripts\generate-android-release-keystore.ps1 -KeytoolPath "C:\Path\To\jdk\bin\keytool.exe"
"@
}

$resolvedOutputDirectory = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($OutputDirectory)
$resolvedKeyPropertiesPath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($KeyPropertiesPath)

New-Item -ItemType Directory -Path $resolvedOutputDirectory -Force | Out-Null

$keystorePath = Join-Path $resolvedOutputDirectory "ble-monitor-release.keystore"
$secretsPath = Join-Path $resolvedOutputDirectory "github-secrets.txt"
$temporaryKeystorePath = "$keystorePath.tmp"

if ((Test-Path -LiteralPath $keystorePath) -and -not $Force) {
    throw "Keystore already exists: $keystorePath. Pass -Force to replace it."
}

if (Test-Path -LiteralPath $temporaryKeystorePath) {
    Remove-Item -LiteralPath $temporaryKeystorePath -Force
}

$storePassword = New-Password
$keyPassword = $storePassword

& $keytool -genkeypair `
    -v `
    -storetype PKCS12 `
    -keystore $temporaryKeystorePath `
    -storepass $storePassword `
    -keypass $keyPassword `
    -alias $Alias `
    -keyalg RSA `
    -keysize 4096 `
    -validity $ValidityDays `
    -dname "CN=BLE Monitor,O=BLE Monitor,C=CN"

if ($LASTEXITCODE -ne 0) {
    if (Test-Path -LiteralPath $temporaryKeystorePath) {
        Remove-Item -LiteralPath $temporaryKeystorePath -Force
    }
    throw "keytool failed with exit code $LASTEXITCODE."
}

Move-Item -LiteralPath $temporaryKeystorePath -Destination $keystorePath -Force

$keystoreBase64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes($keystorePath))
$utf8NoBom = New-Object System.Text.UTF8Encoding $false

$githubSecretsContent = @(
    "ANDROID_RELEASE_KEYSTORE_BASE64=$keystoreBase64"
    "ANDROID_RELEASE_KEYSTORE_PASSWORD=$storePassword"
    "ANDROID_RELEASE_KEY_ALIAS=$Alias"
    "ANDROID_RELEASE_KEY_PASSWORD=$keyPassword"
    ""
    "# Compatible with the RikkaHub sideload workflow secret names:"
    "SIDELOAD_KEYSTORE_BASE64=$keystoreBase64"
    "SIDELOAD_KEYSTORE_PASSWORD=$storePassword"
    "SIDELOAD_KEY_ALIAS=$Alias"
    "SIDELOAD_KEY_PASSWORD=$keyPassword"
)
[IO.File]::WriteAllLines($secretsPath, $githubSecretsContent, $utf8NoBom)

if (-not $SkipLocalProperties) {
    $keyPropertiesDirectory = Split-Path -Parent $resolvedKeyPropertiesPath
    New-Item -ItemType Directory -Path $keyPropertiesDirectory -Force | Out-Null
    $gradleStoreFile = $keystorePath.Replace("\", "/")

    $keyPropertiesContent = @(
        "storePassword=$storePassword"
        "keyPassword=$keyPassword"
        "keyAlias=$Alias"
        "storeFile=$gradleStoreFile"
    )
    [IO.File]::WriteAllLines($resolvedKeyPropertiesPath, $keyPropertiesContent, $utf8NoBom)
}

Write-Host "Keystore created: $keystorePath"
Write-Host "GitHub Secrets file created: $secretsPath"
if (-not $SkipLocalProperties) {
    Write-Host "Local key properties created: $resolvedKeyPropertiesPath"
}
Write-Host "Add each line in github-secrets.txt as a repository secret, then store this directory securely."
