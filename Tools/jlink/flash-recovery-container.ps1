[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$RecoveryContainer,
    [Parameter(Mandatory = $true)][string]$AppMap,
    [string]$LegacyHex = '',
    [string]$RunDirectory = ''
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'jlink-common.ps1')

if ([string]::IsNullOrWhiteSpace($RunDirectory)) {
    $RunDirectory = Join-Path $script:P1RepoRoot ('.cache\p1-5-recovery-{0:yyyyMMdd-HHmmss}' -f (Get-Date))
}
[System.IO.Directory]::CreateDirectory($RunDirectory) | Out-Null
$container = (Resolve-Path $RecoveryContainer).Path
$mapPath = (Resolve-Path $AppMap).Path
$strippedApp = Join-Path $RunDirectory 'recovery-stripped-app.bin'
$tool = Join-Path $script:P1RepoRoot 'Tools\jlink\prepare-bootstrap-app.py'
if ([string]::IsNullOrWhiteSpace($LegacyHex)) {
    $LegacyHex = Join-Path $script:P1RepoRoot 'MDK-ARM_F435\Objects\X-Track.hex'
}
$legacyHex = (Resolve-Path $LegacyHex).Path
$legacyDirectory = Join-Path $RunDirectory 'legacy-preserved'
$preservedLegacy = ''
$deviceModified = $false

Assert-P1File $container
Assert-P1File $mapPath
Assert-P1File $legacyHex
$containerLengthBefore = (Get-Item -LiteralPath $container).Length
$containerHashBefore = (Get-FileHash -LiteralPath $container -Algorithm SHA256).Hash

try {
    $preservedLegacy = Copy-P1PreservedArtifact -SourcePath $legacyHex -DestinationDirectory $legacyDirectory -Role 'selected-legacy'
    Invoke-P1Python -Arguments @(
        $tool, 'prepare', '--input', $container, '--input-kind', 'recovery',
        '--output', $strippedApp
    ) -LogPath (Join-Path $RunDirectory 'recovery-strip.log') | Out-Null

    $containerLengthAfterPrepare = (Get-Item -LiteralPath $container).Length
    $containerHashAfterPrepare = (Get-FileHash -LiteralPath $container -Algorithm SHA256).Hash
    if ($containerLengthAfterPrepare -ne $containerLengthBefore -or
        $containerHashAfterPrepare -ne $containerHashBefore) {
        throw 'Recovery source container changed during trailer removal'
    }
    $strippedLength = (Get-Item -LiteralPath $strippedApp).Length
    if ($containerLengthBefore - $strippedLength -ne 8) {
        throw 'Recovery container did not lose exactly its 8-byte trailer'
    }
    $strippedHash = (Get-FileHash -LiteralPath $strippedApp -Algorithm SHA256).Hash
    Write-Output "P1_5_RECOVERY_TRAILER_STRIPPED=PASS container_len=$containerLengthBefore app_len=$strippedLength bytes_removed=8 app_sha256=$strippedHash source_sha256=$containerHashBefore source_preserved=1"

    $deviceModified = $true
    Invoke-P1FlashApp -AppBin $strippedApp -RunDirectory $RunDirectory -Label 'flash-recovery-app' | Out-Null
    $rttAddress = Get-P1MapRttAddress -MapPath $mapPath
    $resetLogPath = Invoke-P1NormalReset -RunDirectory $RunDirectory -Label 'recovery-ordinary-reset' -WaitMilliseconds 30000 -RttAddress $rttAddress
    $resetEvidence = Assert-P1NormalResetEvidence -LogPath $resetLogPath
    Test-P1RttSignature -Address $rttAddress -RunDirectory $RunDirectory -Label 'recovery-rtt-signature' | Out-Null
    $rttPath = Join-Path $RunDirectory 'recovery-ordinary-reset-rtt.log'
    Invoke-P1RttCapture -Address $rttAddress -OutputPath $rttPath -TimeoutSeconds 15 | Out-Null
    $rttLog = Get-Content -LiteralPath $rttPath -Raw
    if ($rttLog -notmatch 'OTA: HANDOFF vtor=0x08010000') {
        throw 'Recovery ordinary reset RTT evidence lacks the Boot-to-App handoff line'
    }

    $containerLengthAfter = (Get-Item -LiteralPath $container).Length
    $containerHashAfter = (Get-FileHash -LiteralPath $container -Algorithm SHA256).Hash
    if ($containerLengthAfter -ne $containerLengthBefore -or
        $containerHashAfter -ne $containerHashBefore) {
        throw 'Recovery source container changed during deployment'
    }
    Write-Output (
        'P1_5_RECOVERY_FLASH=PASS container={0} stripped={1} pc=0x{2:X8} ' +
        'vtor=0x{3:X8} cfsr=0x{4:X8} rtt=0x{5:X8} source_preserved=1' -f
        $container, $strippedApp, $resetEvidence.PC, $resetEvidence.VTOR,
        $resetEvidence.CFSR, $rttAddress
    )
}
catch {
    $failure = $_
    Write-Warning ("Recovery flashing failed: " + $failure.Exception.Message)
    if ($deviceModified) {
        try {
            if ([string]::IsNullOrWhiteSpace($preservedLegacy) -or
                -not (Test-Path -LiteralPath $preservedLegacy -PathType Leaf)) {
                throw 'The selected preserved legacy HEX is unavailable'
            }
            Invoke-P1LegacyRecovery -LegacyHex $preservedLegacy -RunDirectory $RunDirectory
        }
        catch {
            Write-Warning ("Legacy recovery also failed: " + $_.Exception.Message)
        }
    }
    throw $failure
}
