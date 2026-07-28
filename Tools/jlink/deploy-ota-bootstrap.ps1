[CmdletBinding()]
param(
    [string]$Version = '2.8.0',
    [long]$BuildTimestamp = 0,
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
$preservedLegacyHex = ''
$deviceModified = $false

Assert-P1File $legacyHex
if (Test-Path -LiteralPath $buildDirectory) {
    throw "Fresh build directory already exists: $buildDirectory"
}

try {
    [System.IO.Directory]::CreateDirectory($legacyDirectory) | Out-Null
    $preservedLegacyHex = Copy-P1PreservedArtifact -SourcePath $legacyHex -DestinationDirectory $legacyDirectory -Role 'selected-legacy'
    $repositoryArtifacts = @(
        [pscustomobject]@{
            Path = Join-Path $legacyObjectDirectory 'X-Track.axf'
            Role = 'repo-default-axf'
        },
        [pscustomobject]@{
            Path = Join-Path $legacyObjectDirectory 'X-Track.hex'
            Role = 'repo-default-hex'
        },
        [pscustomobject]@{
            Path = Join-Path $script:P1RepoRoot 'MDK-ARM_F435\Track.bin'
            Role = 'repo-default-bin'
        }
    )
    foreach ($artifact in $repositoryArtifacts) {
        if (Test-Path -LiteralPath $artifact.Path -PathType Leaf) {
            Copy-P1PreservedArtifact -SourcePath $artifact.Path -DestinationDirectory $legacyDirectory -Role $artifact.Role | Out-Null
        }
    }
    Get-ChildItem -LiteralPath $legacyDirectory -File |
        Get-FileHash -Algorithm SHA256 |
        ForEach-Object { '{0}  {1}' -f $_.Hash, $_.Path } |
        Set-Content -LiteralPath $legacyManifest -Encoding ASCII
    $selectedHash = (Get-FileHash -LiteralPath $preservedLegacyHex -Algorithm SHA256).Hash
    Write-Output "P1_5_LEGACY_SNAPSHOT=PASS selected=$preservedLegacyHex sha256=$selectedHash"

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
    Write-Output "P1_5_EXTERNAL_RECOVERY_SLOT=NOT_INSTALLED asset=$recoveryAsset"

    $deviceModified = $true
    Invoke-P1FlashBootAndApp -BootBin $bootBin -AppBin $deployApp -RunDirectory $RunDirectory | Out-Null

    $assetLog = Get-Content -LiteralPath (Join-Path $RunDirectory 'asset-prepare.log') -Raw
    if ($assetLog -notmatch 'P1_5_APP_PREPARE=PASS .*vcode=(\d+)') {
        throw 'Prepared App evidence lacks version_code'
    }
    $expectedVcode = $Matches[1]
    $mapPath = Join-Path $buildDirectory 'app-gcc\X-Track-App-GCC.map'
    $rttAddress = Get-P1MapRttAddress -MapPath $mapPath

    $firstResetLog = Invoke-P1NormalReset -RunDirectory $RunDirectory -Label 'ordinary-reset' -WaitMilliseconds 90000 -RttAddress $rttAddress
    $firstReset = Assert-P1NormalResetEvidence -LogPath $firstResetLog
    Test-P1RttSignature -Address $rttAddress -RunDirectory $RunDirectory -Label 'first-rtt-signature' | Out-Null
    $firstRttPath = Join-Path $RunDirectory 'ordinary-reset-rtt.log'
    Invoke-P1RttCapture -Address $rttAddress -OutputPath $firstRttPath -TimeoutSeconds 30 | Out-Null
    $firstRtt = Get-Content -LiteralPath $firstRttPath -Raw
    if ($firstRtt -notmatch 'OTA: HANDOFF vtor=0x08010000') {
        throw 'Ordinary reset RTT evidence lacks the Boot-to-App handoff line'
    }
    if ($firstRtt -notmatch ('OTA: BCB already CONFIRMED vcode=' + [regex]::Escape($expectedVcode) + '\b')) {
        throw 'First Boot did not establish CONFIRMED with cur_vcode from fw_header'
    }

    $finalResetLog = Invoke-P1NormalReset -RunDirectory $RunDirectory -Label 'final-ordinary-reset' -WaitMilliseconds 90000 -RttAddress $rttAddress
    $finalReset = Assert-P1NormalResetEvidence -LogPath $finalResetLog
    Test-P1RttSignature -Address $rttAddress -RunDirectory $RunDirectory -Label 'final-rtt-signature' | Out-Null
    $finalRttPath = Join-Path $RunDirectory 'final-ordinary-reset-rtt.log'
    Invoke-P1RttCapture -Address $rttAddress -OutputPath $finalRttPath -TimeoutSeconds 30 | Out-Null
    $finalRtt = Get-Content -LiteralPath $finalRttPath -Raw
    if ($finalRtt -notmatch 'OTA: HANDOFF vtor=0x08010000') {
        throw 'Final ordinary reset RTT evidence lacks the Boot-to-App handoff line'
    }
    if ($finalRtt -notmatch ('OTA: BCB already CONFIRMED vcode=' + [regex]::Escape($expectedVcode) + '\b')) {
        throw 'Final ordinary reset RTT evidence lacks the CONFIRMED App vcode'
    }

    Write-Output (
        'P1_5_NORMAL_RESET=PASS pc=0x{0:X8} vtor=0x{1:X8} cfsr=0x{2:X8} ' +
        'final_pc=0x{3:X8} rtt=0x{4:X8} cur_vcode={5}' -f
        $firstReset.PC, $firstReset.VTOR, $firstReset.CFSR,
        $finalReset.PC, $rttAddress, $expectedVcode
    )
    Write-Output "P1_5_DEPLOYMENT=PASS run_directory=$RunDirectory"
}
catch {
    $failure = $_
    Write-Warning ("P1-5 deployment failed: " + $failure.Exception.Message)
    if ($deviceModified) {
        try {
            if ([string]::IsNullOrWhiteSpace($preservedLegacyHex) -or
                -not (Test-Path -LiteralPath $preservedLegacyHex -PathType Leaf)) {
                throw 'The selected preserved legacy HEX is unavailable'
            }
            Invoke-P1LegacyRecovery -LegacyHex $preservedLegacyHex -RunDirectory $RunDirectory
        }
        catch {
            Write-Warning ("Legacy recovery also failed: " + $_.Exception.Message)
        }
    }
    throw $failure
}
