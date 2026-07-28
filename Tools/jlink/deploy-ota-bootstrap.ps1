[CmdletBinding()]
param(
    [string]$Version = '2.8.0',
    [long]$BuildTimestamp = 0,
    [switch]$InstallRecovery,
    [string]$LegacyHex = '',
    [string]$RunDirectory = ''
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'jlink-common.ps1')

if ($BuildTimestamp -eq 0) {
    $BuildTimestamp = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
}
if ([string]::IsNullOrWhiteSpace($RunDirectory)) {
    $RunDirectory = Join-Path $script:P1RepoRoot ('.cache\p1-5-bootstrap-{0:yyyyMMdd-HHmmss}' -f (Get-Date))
}
[System.IO.Directory]::CreateDirectory($RunDirectory) | Out-Null

$legacyObjectDirectory = Join-Path $script:P1RepoRoot 'MDK-ARM_F435\Objects'
if ([string]::IsNullOrWhiteSpace($LegacyHex)) {
    $LegacyHex = Join-Path $legacyObjectDirectory 'X-Track.hex'
}
$legacyHex = (Resolve-Path $LegacyHex).Path
$legacyDirectory = Join-Path $RunDirectory 'legacy-preserved'
$buildDirectory = Join-Path $RunDirectory 'gcc-release'
$rawApp = Join-Path $RunDirectory 'X-Track-App-GCC.raw.bin'
$finalApp = Join-Path $RunDirectory 'X-Track-App-GCC.finalized.bin'
$deployApp = Join-Path $RunDirectory 'X-Track-App-GCC.deploy.bin'
$recoveryAsset = Join-Path $RunDirectory ('recovery-v{0}.bin' -f $Version)
$tool = Join-Path $script:P1RepoRoot 'Tools\jlink\prepare-bootstrap-app.py'
$etuPack = Join-Path $script:P1RepoRoot 'Tools\etu_pack.py'
$cmakeSource = Join-Path $script:P1RepoRoot 'MDK-ARM_F435\cmake-generated'
$armToolchain = 'D:\singlechip\gcc+gdb+openocd\tools\arm-gnu-toolchain-13.3.rel1-ming'
$makeProgram = 'D:\install\mingw64\bin\make.exe'
$legacyManifest = Join-Path $RunDirectory 'legacy-preserved.txt'

Assert-P1File $legacyHex
if (Test-Path -LiteralPath $buildDirectory) {
    throw "Fresh build directory already exists: $buildDirectory"
}
try {
    [System.IO.Directory]::CreateDirectory($legacyDirectory) | Out-Null
    $legacyFiles = @(
        $legacyHex,
        (Join-Path $legacyObjectDirectory 'X-Track.axf'),
        (Join-Path $legacyObjectDirectory 'X-Track.hex'),
        (Join-Path $script:P1RepoRoot 'MDK-ARM_F435\Track.bin')
    )
    foreach ($legacyFile in $legacyFiles) {
        if (Test-Path -LiteralPath $legacyFile -PathType Leaf) {
            Copy-Item -LiteralPath $legacyFile -Destination $legacyDirectory -Force
        }
    }
    Get-ChildItem -LiteralPath $legacyDirectory -File |
        Get-FileHash -Algorithm SHA256 |
        ForEach-Object { '{0}  {1}' -f $_.Hash, $_.Path } |
        Set-Content -LiteralPath $legacyManifest -Encoding ASCII
    Write-Output "P1_5_LEGACY_SNAPSHOT=PASS directory=$legacyDirectory"

    [System.IO.Directory]::CreateDirectory($buildDirectory) | Out-Null
    Invoke-P1Native -FilePath (Get-Command cmake.exe).Source -Arguments @(
        '-S', $cmakeSource,
        '-B', $buildDirectory,
        '-G', 'MinGW Makefiles',
        ('-DCMAKE_MAKE_PROGRAM={0}' -f $makeProgram),
        '-DCMAKE_BUILD_TYPE=Release',
        '-DCMAKE_OBJECT_PATH_MAX=1024',
        ('-DARM_TOOLCHAIN_ROOT={0}' -f $armToolchain)
    ) -LogPath (Join-Path $RunDirectory 'cmake-configure.log') -TimeoutSeconds 180 | Out-Null
    Invoke-P1Native -FilePath (Get-Command cmake.exe).Source -Arguments @(
        '--build', $buildDirectory, '--target', 'X_Track_App_GCC', 'X_Track_Boot',
        '--parallel', '1'
    ) -LogPath (Join-Path $RunDirectory 'cmake-build.log') -TimeoutSeconds 1800 | Out-Null

    $bootBin = Join-Path $buildDirectory 'boot\X-Track-Boot.bin'
    $builtApp = Join-Path $buildDirectory 'app-gcc\X-Track-App-GCC.bin'
    Assert-P1File $bootBin
    Assert-P1File $builtApp
    Copy-Item -LiteralPath $builtApp -Destination $rawApp
    Invoke-P1Python -Arguments @(
        $etuPack, 'finalize', '--app', $rawApp, '--out', $finalApp,
        '--ver-name', $Version, '--build-ts', [string]$BuildTimestamp,
        '--hw-rev', '1', '--layout-id', '1', '--min-boot', '1'
    ) -LogPath (Join-Path $RunDirectory 'finalize.log') | Out-Null
    Invoke-P1Python -Arguments @(
        $tool, 'prepare', '--input', $finalApp, '--input-kind', 'app',
        '--output', $deployApp, '--recovery-output', $recoveryAsset
    ) -LogPath (Join-Path $RunDirectory 'asset-prepare.log') | Out-Null

    $artifactFiles = @(
        $bootBin,
        (Join-Path $buildDirectory 'boot\X-Track-Boot.hex'),
        (Join-Path $buildDirectory 'boot\X-Track-Boot.elf'),
        (Join-Path $buildDirectory 'boot\X-Track-Boot.map'),
        (Join-Path $buildDirectory 'app-gcc\X-Track-App-GCC.bin'),
        (Join-Path $buildDirectory 'app-gcc\X-Track-App-GCC.hex'),
        (Join-Path $buildDirectory 'app-gcc\X-Track-App-GCC.elf'),
        (Join-Path $buildDirectory 'app-gcc\X-Track-App-GCC.map'),
        $deployApp,
        $recoveryAsset
    )
    foreach ($artifact in $artifactFiles) {
        Assert-P1File $artifact
    }
    $artifactManifest = Join-Path $RunDirectory 'artifacts-sha256.txt'
    $artifactFiles | ForEach-Object {
        $hash = Get-FileHash -LiteralPath $_ -Algorithm SHA256
        '{0}  {1}' -f $hash.Hash, $hash.Path
    } | Set-Content -LiteralPath $artifactManifest -Encoding ASCII
    Write-Output "P1_5_FRESH_RELEASE=PASS build=$buildDirectory"

    Invoke-P1FlashBootAndApp -BootBin $bootBin -AppBin $deployApp -RunDirectory $RunDirectory | Out-Null
    Invoke-P1BootstrapCommand -Operation 'clear-bcb' -RunDirectory $RunDirectory -Label 'clear-bcb' | Out-Null
    if ($InstallRecovery) {
        Invoke-P1BootstrapCommand -Operation 'install-recovery' -RunDirectory $RunDirectory -Label 'install-recovery' | Out-Null
    }

    $mapPath = Join-Path $buildDirectory 'app-gcc\X-Track-App-GCC.map'
    $rttAddress = Get-P1MapRttAddress -MapPath $mapPath
    Invoke-P1NormalReset -RunDirectory $RunDirectory -Label 'ordinary-reset' -WaitMilliseconds 30000 -RttAddress $rttAddress | Out-Null
    Test-P1RttSignature -Address $rttAddress -RunDirectory $RunDirectory -Label 'first-rtt-signature' | Out-Null
    Invoke-P1RttCapture -Address $rttAddress -OutputPath (Join-Path $RunDirectory 'ordinary-reset-rtt.log') -TimeoutSeconds 15 | Out-Null
    $resetLog = Get-Content -LiteralPath (Join-Path $RunDirectory 'ordinary-reset.log') -Raw
    $expectedVtor = '{0:X8}' -f $script:P1AppAddress
    if ($resetLog -notmatch ('E000ED08\s*=\s*' + $expectedVtor)) {
        throw "Ordinary reset did not leave VTOR at 0x$expectedVtor"
    }
    $rttLog = Get-Content -LiteralPath (Join-Path $RunDirectory 'ordinary-reset-rtt.log') -Raw
    if ($rttLog -notmatch 'OTA: HANDOFF vtor=0x08010000') {
        throw 'Ordinary reset RTT evidence lacks the Boot-to-App handoff line'
    }
    Invoke-P1BootstrapCommand -Operation 'snapshot-bcb' -RunDirectory $RunDirectory -Label 'first-boot-bcb' | Out-Null
    $assetLog = Get-Content -LiteralPath (Join-Path $RunDirectory 'asset-prepare.log') -Raw
    $snapshotLog = Get-Content -LiteralPath (Join-Path $RunDirectory 'first-boot-bcb-result.log') -Raw
    if ($assetLog -notmatch 'vcode=(\d+)') {
        throw 'Prepared App evidence lacks version_code'
    }
    $expectedVcode = $Matches[1]
    if ($snapshotLog -notmatch 'state=4' -or
        $snapshotLog -notmatch ('cur_vcode=' + $expectedVcode + '(\s|$)')) {
        throw 'First Boot did not persist CONFIRMED with cur_vcode from fw_header'
    }
    Invoke-P1NormalReset -RunDirectory $RunDirectory -Label 'final-ordinary-reset' -WaitMilliseconds 30000 -RttAddress $rttAddress | Out-Null
    Test-P1RttSignature -Address $rttAddress -RunDirectory $RunDirectory -Label 'final-rtt-signature' | Out-Null
    $finalResetLog = Get-Content -LiteralPath (Join-Path $RunDirectory 'final-ordinary-reset.log') -Raw
    if ($finalResetLog -notmatch 'E000ED08\s*=\s*08010000') {
        throw 'Final ordinary reset did not leave VTOR at 0x08010000'
    }
    Write-Output ("P1_5_NORMAL_RESET=PASS vtor=0x{0:X8} rtt=0x{1:X8}" -f $script:P1AppAddress, $rttAddress)
    Write-Output "P1_5_DEPLOYMENT=PASS run_directory=$RunDirectory"
}
catch {
    $failure = $_
    Write-Warning ("P1-5 deployment failed: " + $failure.Exception.Message)
    try {
        $preservedLegacyHex = Join-Path $legacyDirectory (Split-Path -Leaf $legacyHex)
        $recoveryHex = if (Test-Path -LiteralPath $preservedLegacyHex) {
            $preservedLegacyHex
        } else {
            $legacyHex
        }
        Invoke-P1LegacyRecovery -LegacyHex $recoveryHex -RunDirectory $RunDirectory
    }
    catch {
        Write-Warning ("Legacy recovery also failed: " + $_.Exception.Message)
    }
    throw $failure
}
