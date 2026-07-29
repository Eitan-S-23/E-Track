Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'jlink-common.ps1')

$script:P16Protocol = Join-Path $PSScriptRoot 'p1_6_protocol.py'
$script:P16ControlSize = 512
$script:P16ControlAddress = (Get-P1LayoutMacro 'OTA_RAM_ORIGIN') +
    (Get-P1LayoutMacro 'OTA_RAM_LENGTH') - $script:P16ControlSize
$script:P16StatusArmed = 0
$script:P16StatusRunning = 1
$script:P16StatusPass = 2
$script:P16StatusFail = 3
$script:P16StatusCheckpoint = 4
$script:P16OpcodeClearBcb = 1
$script:P16OpcodeInstallSlot = 2
$script:P16OpcodeStageSlots = 3
$script:P16OpcodeSnapshot = 4
$script:P16OpcodeCorruptSlot = 5
$script:P16SlotCandidate = 1
$script:P16SlotBackup = 2
$script:P16SlotRecovery = 4
$script:P16SnapshotBcbOnly = 1
$script:P16MagicCommand = Get-P1LiteralMacro -Path (Join-Path $script:P1RepoRoot 'Libraries\OTA\ota_p1_6_test.h') -Name 'OTA_P1_6_COMMAND_MAGIC'
$script:P16MagicArm = Get-P1LiteralMacro -Path (Join-Path $script:P1RepoRoot 'Libraries\OTA\ota_p1_6_test.h') -Name 'OTA_P1_6_ARM_MAGIC'
$script:P16MagicDone = Get-P1LiteralMacro -Path (Join-Path $script:P1RepoRoot 'Libraries\OTA\ota_p1_6_test.h') -Name 'OTA_P1_6_DONE_MAGIC'
$script:P16OffMagic = 0
$script:P16OffStatus = 44
$script:P16OffTargetCheckpoint = 60

function Invoke-P16Protocol {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)
    $output = & (Get-P1Python) $script:P16Protocol @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "P1-6 protocol tool failed: $($Arguments -join ' ')"
    }
    return $output
}

function Write-P16Json {
    param(
        [Parameter(Mandatory = $true)]$Value,
        [Parameter(Mandatory = $true)][string]$Path
    )
    $json = $Value | ConvertTo-Json -Depth 12
    [System.IO.File]::WriteAllText(
        $Path, $json + [Environment]::NewLine,
        [System.Text.UTF8Encoding]::new($false))
}

function Assert-P16NoJLinkProcess {
    $processes = @(Get-Process -ErrorAction SilentlyContinue | Where-Object {
        $_.ProcessName -like 'JLink*'
    })
    if ($processes.Count -ne 0) {
        $description = ($processes | ForEach-Object {
            '{0}:{1}' -f $_.ProcessName, $_.Id
        }) -join ', '
        throw "A J-Link process is already active: $description"
    }
}

function Invoke-P16JLink {
    param(
        [Parameter(Mandatory = $true)][string[]]$Lines,
        [Parameter(Mandatory = $true)][string]$RunDirectory,
        [Parameter(Mandatory = $true)][string]$Label,
        [int]$TimeoutSeconds = 120
    )
    Assert-P16NoJLinkProcess
    [System.IO.Directory]::CreateDirectory($RunDirectory) | Out-Null
    $commandFile = Join-Path $RunDirectory ($Label + '.jlink')
    $logPath = Join-Path $RunDirectory ($Label + '.log')
    Write-P1JLinkCommandFile -Path $commandFile -Lines $Lines
    try {
        Invoke-P1JLink -CommandFile $commandFile -LogPath $logPath -TimeoutSeconds $TimeoutSeconds | Out-Null
    }
    finally {
        Stop-Process -Name 'JLinkGUIServer' -Force -ErrorAction SilentlyContinue
        Start-Sleep -Milliseconds 250
        Assert-P16NoJLinkProcess
    }
    return $logPath
}

function Get-P16DecodedControl {
    param([Parameter(Mandatory = $true)][string]$Path)
    return (Invoke-P16Protocol @('decode', '--input', $Path) | ConvertFrom-Json)
}

function New-P16EncodedBlock {
    param(
        [Parameter(Mandatory = $true)][ValidateSet('Command', 'Arm')][string]$Kind,
        [Parameter(Mandatory = $true)][string]$RunDirectory,
        [Parameter(Mandatory = $true)][string]$Label,
        [uint32]$Opcode = 0,
        [uint32]$Arg0 = 0,
        [uint32]$Arg1 = 0,
        [uint32]$Arg2 = 0,
        [uint32]$Arg3 = 0,
        [uint32]$Checkpoint = 0
    )
    [System.IO.Directory]::CreateDirectory($RunDirectory) | Out-Null
    $staged = Join-Path $RunDirectory ($Label + '.staged.bin')
    $committed = Join-Path $RunDirectory ($Label + '.committed.bin')
    $magicPath = Join-Path $RunDirectory ($Label + '.magic.txt')
    if ($Kind -eq 'Command') {
        Invoke-P16Protocol @(
            'command', '--opcode', [string]$Opcode,
            '--arg0', [string]$Arg0, '--arg1', [string]$Arg1,
            '--arg2', [string]$Arg2, '--arg3', [string]$Arg3,
            '--output', $staged, '--committed-output', $committed,
            '--magic-output', $magicPath
        ) | Out-Null
    }
    else {
        Invoke-P16Protocol @(
            'arm', '--checkpoint', [string]$Checkpoint,
            '--arg0', [string]$Arg0, '--arg1', [string]$Arg1,
            '--output', $staged, '--committed-output', $committed,
            '--magic-output', $magicPath
        ) | Out-Null
    }

    foreach ($path in @($staged, $committed, $magicPath)) {
        Assert-P1File $path
    }
    $decoded = Get-P16DecodedControl -Path $committed
    $valid = if ($Kind -eq 'Command') {
        [bool]$decoded.command_valid -and
        [uint32]$decoded.magic -eq $script:P16MagicCommand -and
        [uint32]$decoded.opcode -eq $Opcode
    }
    else {
        [bool]$decoded.arm_valid -and
        [uint32]$decoded.magic -eq $script:P16MagicArm -and
        [uint32]$decoded.status -eq $script:P16StatusArmed -and
        [uint32]$decoded.target_checkpoint -eq $Checkpoint -and
        [uint32]$decoded.target_arg0 -eq $Arg0 -and
        [uint32]$decoded.target_arg1 -eq $Arg1
    }
    if (-not $valid) {
        throw "Generated P1-6 $Kind block failed structural validation: $committed"
    }
    $expectedMagic = if ($Kind -eq 'Command') {
        $script:P16MagicCommand
    }
    else {
        $script:P16MagicArm
    }
    $magicText = (Get-Content -LiteralPath $magicPath -Raw).Trim()
    if ([Convert]::ToUInt32($magicText.Substring(2), 16) -ne $expectedMagic) {
        throw "Generated P1-6 magic output mismatch: $magicPath"
    }
    return [pscustomobject]@{
        Kind = $Kind
        Staged = $staged
        Committed = $committed
        Magic = [uint32]$expectedMagic
        Decoded = $decoded
    }
}

function Get-P16WordWriteLines {
    param(
        [Parameter(Mandatory = $true)][string]$StagedBlock,
        [Parameter(Mandatory = $true)][uint32]$Magic,
        [Parameter(Mandatory = $true)][string]$ReadbackPath
    )
    $bytes = [System.IO.File]::ReadAllBytes($StagedBlock)
    if ($bytes.Length -ne $script:P16ControlSize) {
        throw "P1-6 staged block size mismatch: $StagedBlock"
    }
    if ([BitConverter]::ToUInt32($bytes, 0) -ne 0) {
        throw "P1-6 staged block must keep magic zero until the final write"
    }
    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add('h')
    for ($offset = 4; $offset -lt $bytes.Length; $offset += 4) {
        $value = [BitConverter]::ToUInt32($bytes, $offset)
        $lines.Add(('w4 0x{0:X8}, 0x{1:X8}' -f
                    ($script:P16ControlAddress + $offset), $value))
    }
    $lines.Add(('w4 0x{0:X8}, 0x{1:X8}' -f
                $script:P16ControlAddress, $Magic))
    $lines.Add(('savebin "{0}", 0x{1:X8}, 0x{2:X}' -f
                $ReadbackPath, $script:P16ControlAddress,
                $script:P16ControlSize))
    $lines.Add('qc')
    return $lines.ToArray()
}

function Write-P16BlockInPlace {
    param(
        [Parameter(Mandatory = $true)]$Encoded,
        [Parameter(Mandatory = $true)][string]$RunDirectory,
        [Parameter(Mandatory = $true)][string]$Label
    )
    $readback = Join-Path $RunDirectory ($Label + '.write-readback.bin')
    $lines = Get-P16WordWriteLines -StagedBlock $Encoded.Staged `
        -Magic $Encoded.Magic -ReadbackPath $readback
    Invoke-P16JLink -Lines $lines -RunDirectory $RunDirectory `
        -Label ($Label + '-write') -TimeoutSeconds 120 | Out-Null
    Assert-P1File $readback
    $expectedHash = (Get-FileHash -LiteralPath $Encoded.Committed -Algorithm SHA256).Hash
    $actualHash = (Get-FileHash -LiteralPath $readback -Algorithm SHA256).Hash
    if ($expectedHash -ne $actualHash -or
        (Get-Item -LiteralPath $readback).Length -ne $script:P16ControlSize) {
        throw "P1-6 control write readback mismatch: $readback"
    }
    $decoded = Get-P16DecodedControl -Path $readback
    $valid = if ($Encoded.Kind -eq 'Command') {
        [bool]$decoded.command_valid
    }
    else {
        [bool]$decoded.arm_valid -and
        [uint32]$decoded.status -eq $script:P16StatusArmed
    }
    if (-not $valid) {
        throw "P1-6 control readback is structurally invalid: $readback"
    }
    return [pscustomobject]@{ Path = $readback; Decoded = $decoded }
}

function Test-P16CapturedState {
    param(
        [Parameter(Mandatory = $true)]$Decoded,
        [Parameter(Mandatory = $true)][ValidateSet('Done', 'Checkpoint')][string]$Expected,
        [Parameter(Mandatory = $true)][string]$Path,
        [uint32]$Checkpoint = 0,
        [uint32]$Arg0 = 0,
        [uint32]$Arg1 = 0
    )
    if ($Expected -eq 'Done') {
        if ([uint32]$Decoded.magic -eq $script:P16MagicDone) {
            if (-not [bool]$Decoded.result_crc_valid) {
                throw "P1-6 DONE result CRC is invalid: $Path"
            }
            return $true
        }
        if ([uint32]$Decoded.magic -ne $script:P16MagicCommand -or
            [uint32]$Decoded.status -notin @(
                $script:P16StatusArmed, $script:P16StatusRunning)) {
            throw "Unexpected P1-6 command state while polling: $Path"
        }
        return $false
    }

    if ([uint32]$Decoded.magic -ne $script:P16MagicArm -or
        -not [bool]$Decoded.arm_valid) {
        throw "Unexpected P1-6 ARM state while polling: $Path"
    }
    if ([uint32]$Decoded.status -eq $script:P16StatusCheckpoint) {
        if ([uint32]$Decoded.observed_checkpoint -ne $Checkpoint -or
            [uint32]$Decoded.observed_arg0 -ne $Arg0 -or
            [uint32]$Decoded.observed_arg1 -ne $Arg1) {
            throw "P1-6 reached an unexpected checkpoint: $Path"
        }
        return $true
    }
    if ([uint32]$Decoded.status -notin @(
            $script:P16StatusArmed, $script:P16StatusRunning)) {
        throw "Unexpected P1-6 ARM status while polling: $Path"
    }
    return $false
}

function Invoke-P16StartEncodedControl {
    param(
        [Parameter(Mandatory = $true)]$Encoded,
        [Parameter(Mandatory = $true)][ValidateSet('Reset', 'Continue')][string]$StartMode,
        [Parameter(Mandatory = $true)][ValidateSet('Done', 'Checkpoint')][string]$Expected,
        [Parameter(Mandatory = $true)][string]$RunDirectory,
        [Parameter(Mandatory = $true)][string]$Label,
        [int]$PollMilliseconds = 30000,
        [int]$MaxWaitSeconds = 300,
        [uint32]$Checkpoint = 0,
        [uint32]$Arg0 = 0,
        [uint32]$Arg1 = 0
    )
    $wait = [Math]::Min($PollMilliseconds, $MaxWaitSeconds * 1000)
    $readback = Join-Path $RunDirectory ($Label + '.write-readback.bin')
    $capture = Join-Path $RunDirectory ($Label + '.start.bin')
    $coreLines = @(Get-P16WordWriteLines -StagedBlock $Encoded.Staged `
        -Magic $Encoded.Magic -ReadbackPath $readback)
    $lines = New-Object System.Collections.Generic.List[string]
    for ($index = 0; $index -lt ($coreLines.Count - 1); $index++) {
        $lines.Add($coreLines[$index])
    }
    $lines.Add(('verifybin "{0}", 0x{1:X8}' -f
                (Resolve-Path $Encoded.Committed), $script:P16ControlAddress))
    if ($StartMode -eq 'Reset') {
        $lines.Add('r')
    }
    $lines.Add('g')
    $lines.Add(('Sleep {0}' -f $wait))
    $lines.Add('h')
    $lines.Add(('savebin "{0}", 0x{1:X8}, 0x{2:X}' -f
                $capture, $script:P16ControlAddress,
                $script:P16ControlSize))
    $lines.Add('qc')
    $log = Invoke-P16JLink -Lines $lines.ToArray() `
        -RunDirectory $RunDirectory -Label ($Label + '-start') `
        -TimeoutSeconds ([Math]::Ceiling($wait / 1000.0) + 90)

    foreach ($path in @($readback, $capture)) {
        Assert-P1File $path
    }
    $expectedHash = (Get-FileHash -LiteralPath $Encoded.Committed -Algorithm SHA256).Hash
    $actualHash = (Get-FileHash -LiteralPath $readback -Algorithm SHA256).Hash
    if ($expectedHash -ne $actualHash -or
        (Get-Item -LiteralPath $readback).Length -ne $script:P16ControlSize) {
        throw "P1-6 control write readback mismatch before ${StartMode}: $readback"
    }
    $written = Get-P16DecodedControl -Path $readback
    $writeValid = if ($Encoded.Kind -eq 'Command') {
        [bool]$written.command_valid
    }
    else {
        [bool]$written.arm_valid -and
        [uint32]$written.status -eq $script:P16StatusArmed
    }
    if (-not $writeValid) {
        throw "P1-6 control readback was invalid before ${StartMode}: $readback"
    }

    $decoded = Get-P16DecodedControl -Path $capture
    Write-P16Json -Value $decoded -Path ($capture + '.json')
    $complete = Test-P16CapturedState -Decoded $decoded -Expected $Expected `
        -Path $capture -Checkpoint $Checkpoint -Arg0 $Arg0 -Arg1 $Arg1
    if ($complete) {
        return [pscustomobject]@{
            Result = $decoded
            ResultBin = $capture
            Log = $log
            WriteReadback = $readback
            PollCount = 1
            ElapsedMilliseconds = $wait
        }
    }

    $remainingMilliseconds = ($MaxWaitSeconds * 1000) - $wait
    if ($remainingMilliseconds -le 0) {
        throw "P1-6 $Expected wait timed out after $MaxWaitSeconds seconds: $Label"
    }
    $follow = Invoke-P16PollControl -StartMode Continue -Expected $Expected `
        -RunDirectory $RunDirectory -Label ($Label + '-continue') `
        -PollMilliseconds $PollMilliseconds `
        -MaxWaitSeconds ([Math]::Ceiling($remainingMilliseconds / 1000.0)) `
        -Checkpoint $Checkpoint -Arg0 $Arg0 -Arg1 $Arg1
    return [pscustomobject]@{
        Result = $follow.Result
        ResultBin = $follow.ResultBin
        Log = $follow.Log
        WriteReadback = $readback
        PollCount = $follow.PollCount + 1
        ElapsedMilliseconds = $follow.ElapsedMilliseconds + $wait
    }
}

function Invoke-P16PollControl {
    param(
        [Parameter(Mandatory = $true)][ValidateSet('Reset', 'Continue')][string]$StartMode,
        [Parameter(Mandatory = $true)][ValidateSet('Done', 'Checkpoint')][string]$Expected,
        [Parameter(Mandatory = $true)][string]$RunDirectory,
        [Parameter(Mandatory = $true)][string]$Label,
        [int]$PollMilliseconds = 30000,
        [int]$MaxWaitSeconds = 300,
        [uint32]$Checkpoint = 0,
        [uint32]$Arg0 = 0,
        [uint32]$Arg1 = 0
    )
    if ($PollMilliseconds -lt 1000) {
        throw 'P1-6 poll interval must be at least 1000ms'
    }
    $elapsedMilliseconds = 0
    $iteration = 0
    while ($elapsedMilliseconds -lt ($MaxWaitSeconds * 1000)) {
        $iteration++
        $remaining = ($MaxWaitSeconds * 1000) - $elapsedMilliseconds
        $wait = [Math]::Min($PollMilliseconds, $remaining)
        $capture = Join-Path $RunDirectory ('{0}.poll-{1:D2}.bin' -f $Label, $iteration)
        $lines = New-Object System.Collections.Generic.List[string]
        if ($iteration -eq 1 -and $StartMode -eq 'Reset') {
            $lines.Add('r')
        }
        $lines.Add('g')
        $lines.Add(('Sleep {0}' -f $wait))
        $lines.Add('h')
        $lines.Add(('savebin "{0}", 0x{1:X8}, 0x{2:X}' -f
                    $capture, $script:P16ControlAddress,
                    $script:P16ControlSize))
        $lines.Add('qc')
        $pollLabel = '{0}-poll-{1:D2}' -f $Label, $iteration
        $log = Invoke-P16JLink -Lines $lines.ToArray() `
            -RunDirectory $RunDirectory -Label $pollLabel `
            -TimeoutSeconds ([Math]::Ceiling($wait / 1000.0) + 75)
        Assert-P1File $capture
        $decoded = Get-P16DecodedControl -Path $capture
        Write-P16Json -Value $decoded -Path ($capture + '.json')

        if (Test-P16CapturedState -Decoded $decoded -Expected $Expected `
                -Path $capture -Checkpoint $Checkpoint -Arg0 $Arg0 -Arg1 $Arg1) {
            return [pscustomobject]@{
                Result = $decoded
                ResultBin = $capture
                Log = $log
                PollCount = $iteration
                ElapsedMilliseconds = $elapsedMilliseconds + $wait
            }
        }
        $elapsedMilliseconds += $wait
    }
    throw "P1-6 $Expected wait timed out after $MaxWaitSeconds seconds: $Label"
}

function Invoke-P16Command {
    param(
        [Parameter(Mandatory = $true)][uint32]$Opcode,
        [uint32]$Arg0 = 0,
        [uint32]$Arg1 = 0,
        [uint32]$Arg2 = 0,
        [uint32]$Arg3 = 0,
        [Parameter(Mandatory = $true)][string]$RunDirectory,
        [Parameter(Mandatory = $true)][string]$Label,
        [int]$PollMilliseconds = 30000,
        [int]$MaxWaitSeconds = 300,
        [int]$WaitMilliseconds = 0
    )
    if ($WaitMilliseconds -gt 0) {
        $MaxWaitSeconds = [Math]::Max(
            $MaxWaitSeconds, [Math]::Ceiling($WaitMilliseconds / 1000.0))
    }
    $encoded = New-P16EncodedBlock -Kind Command -Opcode $Opcode `
        -Arg0 $Arg0 -Arg1 $Arg1 -Arg2 $Arg2 -Arg3 $Arg3 `
        -RunDirectory $RunDirectory -Label $Label
    $run = Invoke-P16StartEncodedControl -Encoded $encoded `
        -StartMode Reset -Expected Done `
        -RunDirectory $RunDirectory -Label $Label `
        -PollMilliseconds $PollMilliseconds -MaxWaitSeconds $MaxWaitSeconds
    if ([uint32]$run.Result.status -ne $script:P16StatusPass) {
        throw "P1-6 command $Label failed with detail=$($run.Result.detail)"
    }
    return [pscustomobject]@{
        Result = $run.Result
        ResultBin = $run.ResultBin
        Log = $run.Log
        Encoded = $encoded
        WriteReadback = $run.WriteReadback
        PollCount = $run.PollCount
        ElapsedMilliseconds = $run.ElapsedMilliseconds
    }
}

function Set-P16ArmCheckpoint {
    param(
        [Parameter(Mandatory = $true)][uint32]$Checkpoint,
        [uint32]$Arg0 = [uint32]::MaxValue,
        [uint32]$Arg1 = [uint32]::MaxValue,
        [Parameter(Mandatory = $true)][string]$RunDirectory,
        [Parameter(Mandatory = $true)][string]$Label
    )
    $encoded = New-P16EncodedBlock -Kind Arm -Checkpoint $Checkpoint `
        -Arg0 $Arg0 -Arg1 $Arg1 -RunDirectory $RunDirectory -Label $Label
    $write = Write-P16BlockInPlace -Encoded $encoded `
        -RunDirectory $RunDirectory -Label $Label
    return [pscustomobject]@{
        Encoded = $encoded
        WriteReadback = $write.Path
        Decoded = $write.Decoded
    }
}

function Wait-P16Checkpoint {
    param(
        [Parameter(Mandatory = $true)][uint32]$Checkpoint,
        [Parameter(Mandatory = $true)][uint32]$Arg0,
        [Parameter(Mandatory = $true)][uint32]$Arg1,
        [Parameter(Mandatory = $true)][ValidateSet('Reset', 'Continue')][string]$StartMode,
        [Parameter(Mandatory = $true)][string]$RunDirectory,
        [Parameter(Mandatory = $true)][string]$Label,
        [int]$PollMilliseconds = 30000,
        [int]$MaxWaitSeconds = 300
    )
    return Invoke-P16PollControl -StartMode $StartMode -Expected Checkpoint `
        -Checkpoint $Checkpoint -Arg0 $Arg0 -Arg1 $Arg1 `
        -RunDirectory $RunDirectory -Label $Label `
        -PollMilliseconds $PollMilliseconds -MaxWaitSeconds $MaxWaitSeconds
}

function Invoke-P16ArmCheckpoint {
    param(
        [Parameter(Mandatory = $true)][uint32]$Checkpoint,
        [uint32]$Arg0 = [uint32]::MaxValue,
        [uint32]$Arg1 = [uint32]::MaxValue,
        [Parameter(Mandatory = $true)][string]$RunDirectory,
        [Parameter(Mandatory = $true)][string]$Label,
        [int]$PollMilliseconds = 30000,
        [int]$MaxWaitSeconds = 300,
        [int]$WaitMilliseconds = 0
    )
    if ($WaitMilliseconds -gt 0) {
        $MaxWaitSeconds = [Math]::Max(
            $MaxWaitSeconds, [Math]::Ceiling($WaitMilliseconds / 1000.0))
    }
    $encoded = New-P16EncodedBlock -Kind Arm -Checkpoint $Checkpoint `
        -Arg0 $Arg0 -Arg1 $Arg1 -RunDirectory $RunDirectory -Label $Label
    $run = Invoke-P16StartEncodedControl -Encoded $encoded `
        -StartMode Reset -Expected Checkpoint `
        -Checkpoint $Checkpoint -Arg0 $Arg0 -Arg1 $Arg1 `
        -RunDirectory $RunDirectory -Label $Label `
        -PollMilliseconds $PollMilliseconds -MaxWaitSeconds $MaxWaitSeconds
    return [pscustomobject]@{
        Result = $run.Result
        ResultBin = $run.ResultBin
        Log = $run.Log
        Encoded = $encoded
        WriteReadback = $run.WriteReadback
        PollCount = $run.PollCount
        ElapsedMilliseconds = $run.ElapsedMilliseconds
    }
}

function Move-P16Checkpoint {
    param(
        [Parameter(Mandatory = $true)][uint32]$Checkpoint,
        [Parameter(Mandatory = $true)][uint32]$Arg0,
        [Parameter(Mandatory = $true)][uint32]$Arg1,
        [Parameter(Mandatory = $true)][ValidateSet('Reset', 'Continue')][string]$StartMode,
        [Parameter(Mandatory = $true)][string]$RunDirectory,
        [Parameter(Mandatory = $true)][string]$Label,
        [int]$PollMilliseconds = 30000,
        [int]$MaxWaitSeconds = 300
    )
    $encoded = New-P16EncodedBlock -Kind Arm -Checkpoint $Checkpoint `
        -Arg0 $Arg0 -Arg1 $Arg1 -RunDirectory $RunDirectory -Label $Label
    $run = Invoke-P16StartEncodedControl -Encoded $encoded `
        -StartMode $StartMode -Expected Checkpoint `
        -Checkpoint $Checkpoint -Arg0 $Arg0 -Arg1 $Arg1 `
        -RunDirectory $RunDirectory -Label $Label `
        -PollMilliseconds $PollMilliseconds -MaxWaitSeconds $MaxWaitSeconds
    return [pscustomobject]@{
        Result = $run.Result
        ResultBin = $run.ResultBin
        Log = $run.Log
        Encoded = $encoded
        WriteReadback = $run.WriteReadback
        PollCount = $run.PollCount
        ElapsedMilliseconds = $run.ElapsedMilliseconds
    }
}

function Release-P16Checkpoint {
    param(
        [Parameter(Mandatory = $true)][string]$RunDirectory,
        [Parameter(Mandatory = $true)][string]$Label
    )
    Invoke-P16JLink -Lines @(
        'h',
        ('w4 0x{0:X8}, 0x{1:X8}' -f
         ($script:P16ControlAddress + $script:P16OffStatus),
         $script:P16StatusRunning),
        'g', 'qc'
    ) -RunDirectory $RunDirectory -Label $Label -TimeoutSeconds 60 | Out-Null
}

function Save-P16Control {
    param(
        [Parameter(Mandatory = $true)][string]$RunDirectory,
        [Parameter(Mandatory = $true)][string]$Label,
        [switch]$Resume
    )
    $output = Join-Path $RunDirectory ($Label + '.control.bin')
    $lines = @(
        'h',
        ('savebin "{0}", 0x{1:X8}, 0x{2:X}' -f
         $output, $script:P16ControlAddress, $script:P16ControlSize)
    )
    if ($Resume) {
        $lines += 'g'
    }
    $lines += 'qc'
    Invoke-P16JLink -Lines $lines -RunDirectory $RunDirectory `
        -Label ($Label + '-capture') -TimeoutSeconds 60 | Out-Null
    Assert-P1File $output
    return $output
}

function Save-P16InternalImage {
    param(
        [Parameter(Mandatory = $true)][uint32]$Length,
        [Parameter(Mandatory = $true)][string]$RunDirectory,
        [Parameter(Mandatory = $true)][string]$Label
    )
    $output = Join-Path $RunDirectory ($Label + '.bin')
    Invoke-P16JLink -Lines @(
        'h',
        ('savebin "{0}", 0x{1:X8}, 0x{2:X}' -f
         $output, $script:P1AppAddress, $Length),
        'qc'
    ) -RunDirectory $RunDirectory -Label ($Label + '-capture') `
        -TimeoutSeconds 120 | Out-Null
    Assert-P1File $output
    $record = [ordered]@{
        path = $output
        length = (Get-Item -LiteralPath $output).Length
        raw_sha256 = (Get-FileHash -LiteralPath $output -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    Write-P16Json -Value $record -Path (Join-Path $RunDirectory ($Label + '.json'))
    return [pscustomobject]$record
}

function Save-P16MemoryRange {
    param(
        [Parameter(Mandatory = $true)][uint32]$Address,
        [Parameter(Mandatory = $true)][uint32]$Length,
        [Parameter(Mandatory = $true)][string]$RunDirectory,
        [Parameter(Mandatory = $true)][string]$Label
    )
    $output = Join-Path $RunDirectory ($Label + '.bin')
    Invoke-P16JLink -Lines @(
        'h',
        ('savebin "{0}", 0x{1:X8}, 0x{2:X}' -f
         $output, $Address, $Length),
        'qc'
    ) -RunDirectory $RunDirectory -Label ($Label + '-capture') `
        -TimeoutSeconds 90 | Out-Null
    Assert-P1File $output
    return $output
}

function Invoke-P16FlashApp {
    param(
        [Parameter(Mandatory = $true)][string]$AppBin,
        [Parameter(Mandatory = $true)][string]$RunDirectory,
        [Parameter(Mandatory = $true)][string]$Label
    )
    Assert-P1File $AppBin
    $log = Invoke-P16JLink -Lines @(
        'h',
        ('loadbin "{0}", 0x{1:X8}' -f
         (Resolve-Path $AppBin), $script:P1AppAddress),
        ('verifybin "{0}", 0x{1:X8}' -f
         (Resolve-Path $AppBin), $script:P1AppAddress),
        'qc'
    ) -RunDirectory $RunDirectory -Label $Label -TimeoutSeconds 180
    $text = Get-Content -LiteralPath $log -Raw
    if ([regex]::Matches($text, 'Verify successful\.').Count -ne 1) {
        throw "P1-6 App flash verification failed: $log"
    }
    return $log
}

function Invoke-P16OrdinaryResetEvidence {
    param(
        [Parameter(Mandatory = $true)][string]$RunDirectory,
        [Parameter(Mandatory = $true)][string]$Label,
        [int]$WaitMilliseconds = 5000
    )
    $log = Invoke-P16JLink -Lines @(
        'r', 'g', ('Sleep {0}' -f $WaitMilliseconds), 'h', 'regs',
        'mem32 0xE000ED08, 1',
        'mem32 0xE000ED28, 1',
        'g', 'qc'
    ) -RunDirectory $RunDirectory -Label $Label `
        -TimeoutSeconds ([Math]::Ceiling($WaitMilliseconds / 1000.0) + 75)
    $evidence = Assert-P1NormalResetEvidence -LogPath $log
    $record = [ordered]@{
        pc = ('0x{0:X8}' -f $evidence.PC)
        vtor = ('0x{0:X8}' -f $evidence.VTOR)
        cfsr = ('0x{0:X8}' -f $evidence.CFSR)
        log = $log
    }
    Write-P16Json -Value $record -Path (Join-Path $RunDirectory ($Label + '.json'))
    return [pscustomobject]$record
}
