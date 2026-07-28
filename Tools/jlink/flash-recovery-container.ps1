[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$RecoveryContainer,
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
$strippedApp = Join-Path $RunDirectory 'recovery-stripped-app.bin'
$tool = Join-Path $script:P1RepoRoot 'Tools\jlink\prepare-bootstrap-app.py'
if ([string]::IsNullOrWhiteSpace($LegacyHex)) {
    $LegacyHex = Join-Path $script:P1RepoRoot 'MDK-ARM_F435\Objects\X-Track.hex'
}
$legacyHex = (Resolve-Path $LegacyHex).Path
$preservedLegacy = Join-Path $RunDirectory 'legacy-X-Track.hex'
Copy-Item -LiteralPath $legacyHex -Destination $preservedLegacy

try {
    Invoke-P1Python -Arguments @(
        $tool, 'prepare', '--input', $container, '--input-kind', 'recovery',
        '--output', $strippedApp
    ) -LogPath (Join-Path $RunDirectory 'recovery-strip.log') | Out-Null
    $containerLength = (Get-Item -LiteralPath $container).Length
    $strippedLength = (Get-Item -LiteralPath $strippedApp).Length
    if ($containerLength - $strippedLength -ne 8) {
        throw "Recovery container did not lose exactly its 8-byte trailer"
    }
    $strippedHash = (Get-FileHash -LiteralPath $strippedApp -Algorithm SHA256).Hash
    Write-Output "P1_5_RECOVERY_TRAILER_STRIPPED=PASS container_len=$containerLength app_len=$strippedLength bytes_removed=8 app_sha256=$strippedHash"
    Invoke-P1FlashApp -AppBin $strippedApp -RunDirectory $RunDirectory -Label 'flash-recovery-app' | Out-Null
    Invoke-P1BootstrapCommand -Operation 'clear-bcb' -RunDirectory $RunDirectory -Label 'recovery-clear-bcb' | Out-Null
    $resetLogPath = Invoke-P1NormalReset -RunDirectory $RunDirectory -Label 'recovery-ordinary-reset' -WaitMilliseconds 30000
    $resetLog = Get-Content -LiteralPath $resetLogPath -Raw
    $expectedVtor = '{0:X8}' -f $script:P1AppAddress
    if ($resetLog -notmatch ('E000ED08\s*=\s*' + $expectedVtor)) {
        throw "Recovery ordinary reset did not leave VTOR at 0x$expectedVtor"
    }
    Write-Output "P1_5_RECOVERY_FLASH=PASS container=$container stripped=$strippedApp"
}
catch {
    $failure = $_
    Write-Warning ("Recovery flashing failed: " + $failure.Exception.Message)
    try {
        Invoke-P1LegacyRecovery -LegacyHex $preservedLegacy -RunDirectory $RunDirectory
    }
    catch {
        Write-Warning ("Legacy recovery also failed: " + $_.Exception.Message)
    }
    throw $failure
}
