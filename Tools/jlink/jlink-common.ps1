Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$script:P1RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path

function Get-P1LiteralMacro {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Name
    )
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Macro source header is absent: $Path"
    }
    $headerText = Get-Content -LiteralPath $Path -Raw
    $pattern = '(?m)^\s*#define\s+{0}\s+(0x[0-9A-Fa-f]+|[0-9]+)[uUlL]*\s*$' -f [regex]::Escape($Name)
    $match = [regex]::Match($headerText, $pattern)
    if (-not $match.Success) {
        throw "Header macro is absent or non-literal: $Name"
    }
    $value = $match.Groups[1].Value
    if ($value.StartsWith('0x', [System.StringComparison]::OrdinalIgnoreCase)) {
        return [Convert]::ToUInt32($value.Substring(2), 16)
    }
    return [Convert]::ToUInt32($value, 10)
}

function Get-P1LayoutMacro {
    param([Parameter(Mandatory = $true)][string]$Name)
    return Get-P1LiteralMacro -Path (Join-Path $script:P1RepoRoot 'Libraries\OTA\ota_layout.h') -Name $Name
}

$script:P1JLinkExe = 'C:\Users\SU\SEGGER\JLink_V818\JLink.exe'
$script:P1RttLoggerExe = 'C:\Users\SU\SEGGER\JLink_V818\JLinkRTTLogger.exe'
$script:P1Device = 'AT32F435RGT7'
$script:P1SpeedKHz = 1000
$script:P1BootAddress = Get-P1LayoutMacro 'OTA_BOOT_ORIGIN'
$script:P1AppAddress = Get-P1LayoutMacro 'OTA_APP_ORIGIN'
$script:P1AppLength = Get-P1LayoutMacro 'OTA_APP_LENGTH'

function Assert-P1File {
    param([Parameter(Mandatory = $true)][string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Required file is absent: $Path"
    }
}

function Copy-P1PreservedArtifact {
    param(
        [Parameter(Mandatory = $true)][string]$SourcePath,
        [Parameter(Mandatory = $true)][string]$DestinationDirectory,
        [Parameter(Mandatory = $true)]
        [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._-]*$')]
        [string]$Role
    )
    Assert-P1File $SourcePath
    $source = (Resolve-Path $SourcePath).Path
    [System.IO.Directory]::CreateDirectory($DestinationDirectory) | Out-Null
    $sourceHash = Get-FileHash -LiteralPath $source -Algorithm SHA256
    $sourceLength = (Get-Item -LiteralPath $source).Length
    $targetName = '{0}-{1}-{2}' -f $Role, $sourceHash.Hash.ToLowerInvariant(),
        [System.IO.Path]::GetFileName($source)
    $target = Join-Path $DestinationDirectory $targetName
    if ([string]::Equals(
            [System.IO.Path]::GetFullPath($source),
            [System.IO.Path]::GetFullPath($target),
            [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Preserved artifact destination resolves to its source: $source"
    }
    if (Test-Path -LiteralPath $target) {
        throw "Preserved artifact destination already exists: $target"
    }
    Copy-Item -LiteralPath $source -Destination $target
    $targetHash = Get-FileHash -LiteralPath $target -Algorithm SHA256
    $targetLength = (Get-Item -LiteralPath $target).Length
    if ($targetLength -ne $sourceLength -or $targetHash.Hash -ne $sourceHash.Hash) {
        throw "Preserved artifact readback mismatch: $target"
    }
    return (Resolve-Path $target).Path
}

function ConvertTo-P1NativeArgument {
    param([Parameter(Mandatory = $true)][string]$Value)
    if ($Value.Length -eq 0) {
        return '""'
    }
    if ($Value -notmatch '[\s"]') {
        return $Value
    }
    return '"' + $Value.Replace('"', '\"') + '"'
}

function Invoke-P1Native {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$LogPath,
        [int]$TimeoutSeconds = 120
    )
    Assert-P1File $FilePath
    $logDirectory = Split-Path -Parent $LogPath
    [System.IO.Directory]::CreateDirectory($logDirectory) | Out-Null
    $argumentLine = ($Arguments | ForEach-Object {
        ConvertTo-P1NativeArgument ([string]$_)
    }) -join ' '
    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $FilePath
    $startInfo.Arguments = $argumentLine
    $startInfo.WorkingDirectory = $script:P1RepoRoot
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $startInfo
    if (-not $process.Start()) {
        throw "Failed to start: $FilePath"
    }
    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()
    if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
        $process.Kill()
        $process.WaitForExit()
        [System.IO.File]::WriteAllText($LogPath, "P1_5_PROCESS_TIMEOUT file=$FilePath timeout_seconds=$TimeoutSeconds", [System.Text.UTF8Encoding]::new($false))
        throw "Timed out after $TimeoutSeconds seconds: $FilePath"
    }
    $stdout = $stdoutTask.GetAwaiter().GetResult()
    $stderr = $stderrTask.GetAwaiter().GetResult()
    [System.IO.File]::WriteAllText($LogPath, $stdout + $stderr, [System.Text.UTF8Encoding]::new($false))
    if ($process.ExitCode -ne 0) {
        throw "Process failed ($($process.ExitCode)): $FilePath. See $LogPath"
    }
    return [pscustomobject]@{ ExitCode = $process.ExitCode; LogPath = $LogPath }
}

function Get-P1Python {
    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($null -eq $python) {
        $python = Get-Command python -ErrorAction Stop
    }
    return $python.Source
}

function Invoke-P1Python {
    param(
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$LogPath,
        [int]$TimeoutSeconds = 120
    )
    return Invoke-P1Native -FilePath (Get-P1Python) -Arguments $Arguments -LogPath $LogPath -TimeoutSeconds $TimeoutSeconds
}

function Write-P1JLinkCommandFile {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string[]]$Lines
    )
    [System.IO.Directory]::CreateDirectory((Split-Path -Parent $Path)) | Out-Null
    [System.IO.File]::WriteAllLines($Path, $Lines, [System.Text.ASCIIEncoding]::new())
}

function Invoke-P1JLink {
    param(
        [Parameter(Mandatory = $true)][string]$CommandFile,
        [Parameter(Mandatory = $true)][string]$LogPath,
        [int]$TimeoutSeconds = 120
    )
    return Invoke-P1Native -FilePath $script:P1JLinkExe -Arguments @(
        '-Device', $script:P1Device, '-If', 'SWD', '-Speed',
        [string]$script:P1SpeedKHz, '-AutoConnect', '1', '-ExitOnError',
        '1', '-CommandFile', $CommandFile
    ) -LogPath $LogPath -TimeoutSeconds $TimeoutSeconds
}

function Invoke-P1FlashBootAndApp {
    param(
        [Parameter(Mandatory = $true)][string]$BootBin,
        [Parameter(Mandatory = $true)][string]$AppBin,
        [Parameter(Mandatory = $true)][string]$RunDirectory
    )
    Assert-P1File $BootBin
    Assert-P1File $AppBin
    $commandFile = Join-Path $RunDirectory 'flash-boot-and-app.jlink'
    $logPath = Join-Path $RunDirectory 'flash-boot-and-app.log'
    Write-P1JLinkCommandFile -Path $commandFile -Lines @(
        'h',
        ('loadbin "{0}", 0x{1:X8}' -f (Resolve-Path $BootBin), $script:P1BootAddress),
        ('verifybin "{0}", 0x{1:X8}' -f (Resolve-Path $BootBin), $script:P1BootAddress),
        ('loadbin "{0}", 0x{1:X8}' -f (Resolve-Path $AppBin), $script:P1AppAddress),
        ('verifybin "{0}", 0x{1:X8}' -f (Resolve-Path $AppBin), $script:P1AppAddress),
        'qc'
    )
    Invoke-P1JLink -CommandFile $commandFile -LogPath $logPath -TimeoutSeconds 180 | Out-Null
    $log = Get-Content -LiteralPath $logPath -Raw
    $verifyCount = [regex]::Matches($log, 'Verify successful\.').Count
    if ($verifyCount -ne 2) {
        throw "J-Link did not report both Boot and App VerifyBin successes. See $logPath"
    }
    Write-Output ('P1_5_FLASH_VERIFY=PASS boot=0x{0:X8} app=0x{1:X8}' -f $script:P1BootAddress, $script:P1AppAddress)
    return $logPath
}

function Invoke-P1FlashApp {
    param(
        [Parameter(Mandatory = $true)][string]$AppBin,
        [Parameter(Mandatory = $true)][string]$RunDirectory,
        [string]$Label = 'flash-app'
    )
    Assert-P1File $AppBin
    $commandFile = Join-Path $RunDirectory ($Label + '.jlink')
    $logPath = Join-Path $RunDirectory ($Label + '.log')
    Write-P1JLinkCommandFile -Path $commandFile -Lines @(
        'h',
        ('loadbin "{0}", 0x{1:X8}' -f (Resolve-Path $AppBin), $script:P1AppAddress),
        ('verifybin "{0}", 0x{1:X8}' -f (Resolve-Path $AppBin), $script:P1AppAddress),
        'qc'
    )
    Invoke-P1JLink -CommandFile $commandFile -LogPath $logPath -TimeoutSeconds 180 | Out-Null
    $log = Get-Content -LiteralPath $logPath -Raw
    if ([regex]::Matches($log, 'Verify successful\.').Count -ne 1) {
        throw "J-Link App VerifyBin did not report success. See $logPath"
    }
    Write-Output ('P1_5_APP_FLASH_VERIFY=PASS app=0x{0:X8} trailer_written=0' -f $script:P1AppAddress)
    return $logPath
}

function Invoke-P1LegacyRecovery {
    param(
        [Parameter(Mandatory = $true)][string]$LegacyHex,
        [Parameter(Mandatory = $true)][string]$RunDirectory
    )
    Assert-P1File $LegacyHex
    $commandFile = Join-Path $RunDirectory 'restore-legacy.jlink'
    $logPath = Join-Path $RunDirectory 'restore-legacy.log'
    Write-P1JLinkCommandFile -Path $commandFile -Lines @(
        'h', ('loadfile "{0}"' -f (Resolve-Path $LegacyHex)), 'r', 'g', 'qc'
    )
    Invoke-P1JLink -CommandFile $commandFile -LogPath $logPath -TimeoutSeconds 180 | Out-Null
    Write-Output "P1_5_LEGACY_RECOVERY=PASS source=$LegacyHex"
}

function Invoke-P1NormalReset {
    param(
        [Parameter(Mandatory = $true)][string]$RunDirectory,
        [string]$Label = 'ordinary-reset',
        [int]$WaitMilliseconds = 1500,
        [uint32]$RttAddress = 0
    )
    $commandFile = Join-Path $RunDirectory ($Label + '.jlink')
    $logPath = Join-Path $RunDirectory ($Label + '.log')
    $lines = @(
        'r', 'g', ('Sleep {0}' -f $WaitMilliseconds), 'h', 'regs',
        'mem32 0xE000ED08, 1',
        'mem32 0xE000ED28, 1'
    )
    if ($RttAddress -ne 0) {
        $lines += ('mem8 0x{0:X8}, 16' -f $RttAddress)
    }
    $lines += @('g', 'qc')
    Write-P1JLinkCommandFile -Path $commandFile -Lines $lines
    $timeoutSeconds = [Math]::Ceiling($WaitMilliseconds / 1000.0) + 60
    Invoke-P1JLink -CommandFile $commandFile -LogPath $logPath -TimeoutSeconds $timeoutSeconds | Out-Null
    return $logPath
}

function Get-P1LogHex32 {
    param(
        [Parameter(Mandatory = $true)][string]$Text,
        [Parameter(Mandatory = $true)][string]$Pattern,
        [Parameter(Mandatory = $true)][string]$Label
    )
    $matches = [regex]::Matches(
        $Text,
        $Pattern,
        [System.Text.RegularExpressions.RegexOptions]::IgnoreCase -bor
        [System.Text.RegularExpressions.RegexOptions]::Multiline
    )
    if ($matches.Count -eq 0) {
        throw "Expected at least one $Label value in the J-Link reset log"
    }
    return [Convert]::ToUInt32(
        $matches[$matches.Count - 1].Groups[1].Value,
        16
    )
}

function Assert-P1NormalResetEvidence {
    param(
        [Parameter(Mandatory = $true)][string]$LogPath,
        [uint32]$ExpectedVtor = $script:P1AppAddress
    )
    Assert-P1File $LogPath
    $log = Get-Content -LiteralPath $LogPath -Raw
    $pc = Get-P1LogHex32 -Text $log -Pattern '^\s*PC\s*=\s*(?:0x)?([0-9A-Fa-f]{8})\b' -Label 'PC'
    $vtor = Get-P1LogHex32 -Text $log -Pattern '^\s*E000ED08\s*=\s*(?:0x)?([0-9A-Fa-f]{8})\b' -Label 'VTOR'
    $cfsr = Get-P1LogHex32 -Text $log -Pattern '^\s*E000ED28\s*=\s*(?:0x)?([0-9A-Fa-f]{8})\b' -Label 'CFSR'
    $appEnd = [uint64]$script:P1AppAddress + [uint64]$script:P1AppLength

    if ([uint64]$pc -lt [uint64]$script:P1AppAddress -or
        [uint64]$pc -ge $appEnd) {
        throw ('Ordinary reset PC is outside the App partition: 0x{0:X8}' -f $pc)
    }
    if ($vtor -ne $ExpectedVtor) {
        throw ('Ordinary reset VTOR mismatch: got 0x{0:X8}, expected 0x{1:X8}' -f $vtor, $ExpectedVtor)
    }
    if ($cfsr -ne 0) {
        throw ('Ordinary reset CFSR is nonzero: 0x{0:X8}' -f $cfsr)
    }

    return [pscustomobject]@{
        PC = $pc
        VTOR = $vtor
        CFSR = $cfsr
    }
}

function Format-P1NormalResetPassLine {
    param(
        [Parameter(Mandatory = $true)][uint32]$PC,
        [Parameter(Mandatory = $true)][uint32]$VTOR,
        [Parameter(Mandatory = $true)][uint32]$CFSR,
        [Parameter(Mandatory = $true)][uint32]$FinalPC,
        [Parameter(Mandatory = $true)][uint32]$FinalVTOR,
        [Parameter(Mandatory = $true)][uint32]$FinalCFSR,
        [Parameter(Mandatory = $true)][uint32]$RttAddress,
        [Parameter(Mandatory = $true)][string]$CurVcode
    )
    $format = (
        'P1_5_NORMAL_RESET=PASS pc=0x{0:X8} vtor=0x{1:X8} cfsr=0x{2:X8} ' +
        'final_pc=0x{3:X8} final_vtor=0x{4:X8} final_cfsr=0x{5:X8} ' +
        'rtt=0x{6:X8} cur_vcode={7}'
    )
    return $format -f $PC, $VTOR, $CFSR, $FinalPC, $FinalVTOR,
        $FinalCFSR, $RttAddress, $CurVcode
}

function Format-P1RecoveryFlashPassLine {
    param(
        [Parameter(Mandatory = $true)][string]$Container,
        [Parameter(Mandatory = $true)][string]$StrippedApp,
        [Parameter(Mandatory = $true)][uint32]$PC,
        [Parameter(Mandatory = $true)][uint32]$VTOR,
        [Parameter(Mandatory = $true)][uint32]$CFSR,
        [Parameter(Mandatory = $true)][uint32]$RttAddress
    )
    $format = (
        'P1_5_RECOVERY_FLASH=PASS container={0} stripped={1} pc=0x{2:X8} ' +
        'vtor=0x{3:X8} cfsr=0x{4:X8} rtt=0x{5:X8} source_preserved=1'
    )
    return $format -f $Container, $StrippedApp, $PC, $VTOR, $CFSR,
        $RttAddress
}

function Stop-P1RttLogger {
    Get-Process -Name 'JLinkRTTLogger' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 250
    if (Get-Process -Name 'JLinkRTTLogger' -ErrorAction SilentlyContinue) {
        throw 'JLinkRTTLogger remained after cleanup'
    }
}

function Assert-P1NoRttViewer {
    if (Get-Process -Name 'JLinkRTTViewer' -ErrorAction SilentlyContinue) {
        throw 'Close JLinkRTTViewer before collecting the exclusive RTT evidence'
    }
}

function Get-P1MapRttAddress {
    param([Parameter(Mandatory = $true)][string]$MapPath)
    Assert-P1File $MapPath
    $symbolLines = @(Get-Content -LiteralPath $MapPath | Where-Object {
        $_ -match '^\s*(0x[0-9A-Fa-f]+)\s+_SEGGER_RTT\s*$'
    })
    if ($symbolLines.Count -ne 1) {
        throw "Expected one exact _SEGGER_RTT map symbol, found $($symbolLines.Count)"
    }
    $null = $symbolLines[0] -match '^\s*(0x[0-9A-Fa-f]+)\s+_SEGGER_RTT\s*$'
    return [Convert]::ToUInt32($Matches[1], 16)
}

function Test-P1RttSignature {
    param(
        [Parameter(Mandatory = $true)][uint32]$Address,
        [Parameter(Mandatory = $true)][string]$RunDirectory,
        [string]$Label = 'rtt-signature'
    )
    $commandFile = Join-Path $RunDirectory ($Label + '.jlink')
    $logPath = Join-Path $RunDirectory ($Label + '.log')
    Write-P1JLinkCommandFile -Path $commandFile -Lines @(
        'h', ('mem8 0x{0:X8}, 16' -f $Address), 'g', 'qc'
    )
    Invoke-P1JLink -CommandFile $commandFile -LogPath $logPath -TimeoutSeconds 60 | Out-Null
    $log = Get-Content -LiteralPath $logPath -Raw
    if ($log -notmatch '=\s*53 45 47 47 45 52 20 52 54 54') {
        throw "RTT signature mismatch at 0x$('{0:X8}' -f $Address). See $logPath"
    }
    Write-Output ("P1_5_RTT_SIGNATURE=PASS address=0x{0:X8}" -f $Address)
    return $logPath
}

function Invoke-P1RttCapture {
    param(
        [Parameter(Mandatory = $true)][uint32]$Address,
        [Parameter(Mandatory = $true)][string]$OutputPath,
        [int]$TimeoutSeconds = 15
    )
    Assert-P1NoRttViewer
    Stop-P1RttLogger
    $stdoutPath = $OutputPath + '.stdout'
    $stderrPath = $OutputPath + '.stderr'
    [System.IO.Directory]::CreateDirectory((Split-Path -Parent $OutputPath)) | Out-Null
    $arguments = @(
        '-Device', 'CORTEX-M4', '-If', 'SWD', '-Speed',
        [string]$script:P1SpeedKHz, '-RTTAddress', ('0x{0:X8}' -f $Address),
        '-RTTChannel', '0', $OutputPath
    )
    $argumentLine = ($arguments | ForEach-Object {
        ConvertTo-P1NativeArgument ([string]$_)
    }) -join ' '
    $process = Start-Process -FilePath $script:P1RttLoggerExe -ArgumentList $argumentLine -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath
    try {
        if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
            $process.Kill()
            $process.WaitForExit()
        }
    }
    finally {
        Stop-P1RttLogger
    }
    Write-Output "P1_5_RTT_CAPTURE=PASS address=0x$('{0:X8}' -f $Address) seconds=$TimeoutSeconds"
}
