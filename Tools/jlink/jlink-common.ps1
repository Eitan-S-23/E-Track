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
$script:P1BootstrapAddress = Get-P1LayoutMacro 'OTA_OVERLAY_ORIGIN'
$script:P1BootstrapLength = Get-P1LiteralMacro -Path (Join-Path $script:P1RepoRoot 'boot\include\boot_bootstrap.h') -Name 'BOOT_BOOTSTRAP_COMMAND_SIZE'

function Assert-P1File {
    param([Parameter(Mandatory = $true)][string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Required file is absent: $Path"
    }
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

function Invoke-P1BootstrapCommand {
    param(
        [Parameter(Mandatory = $true)][ValidateSet('clear-bcb', 'install-candidate', 'install-backup', 'install-recovery', 'stage-slots', 'snapshot-bcb')][string]$Operation,
        [Parameter(Mandatory = $true)][string]$RunDirectory,
        [string]$Label = $Operation,
        [int]$WaitMilliseconds = 0
    )
    if ($WaitMilliseconds -eq 0) {
        if ($Operation -like 'install-*' -or $Operation -eq 'stage-slots') {
            $WaitMilliseconds = 180000
        } else {
            $WaitMilliseconds = 10000
        }
    }
    $tool = Join-Path $script:P1RepoRoot 'Tools\jlink\prepare-bootstrap-app.py'
    $commandBin = Join-Path $RunDirectory ($Label + '-command.bin')
    $resultBin = Join-Path $RunDirectory ($Label + '-result.bin')
    $commandFile = Join-Path $RunDirectory ($Label + '.jlink')
    $commandLog = Join-Path $RunDirectory ($Label + '.log')
    $prepareLog = Join-Path $RunDirectory ($Label + '-command.log')
    $resultLog = Join-Path $RunDirectory ($Label + '-result.log')
    Invoke-P1Python -Arguments @($tool, 'command', '--operation', $Operation, '--output', $commandBin) -LogPath $prepareLog | Out-Null
    Write-P1JLinkCommandFile -Path $commandFile -Lines @(
        'h',
        ('loadbin "{0}", 0x{1:X8}' -f $commandBin, $script:P1BootstrapAddress),
        'r',
        'g',
        ('Sleep {0}' -f $WaitMilliseconds),
        'h',
        ('savebin "{0}", 0x{1:X8}, 0x{2:X}' -f $resultBin, $script:P1BootstrapAddress, $script:P1BootstrapLength),
        'qc'
    )
    $timeoutSeconds = [Math]::Ceiling($WaitMilliseconds / 1000.0) + 60
    Invoke-P1JLink -CommandFile $commandFile -LogPath $commandLog -TimeoutSeconds $timeoutSeconds | Out-Null
    Invoke-P1Python -Arguments @($tool, 'result', '--input', $resultBin) -LogPath $resultLog | Out-Null
    Get-Content -LiteralPath $resultLog
    return $resultBin
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
    if ($log -notmatch 'Verify successful\.') {
        throw "J-Link VerifyBin did not report success. See $logPath"
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
    if ((Get-Content -LiteralPath $logPath -Raw) -notmatch 'Verify successful\.') {
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
