[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$BootBin,
    [Parameter(Mandatory = $true)][string]$AppBin,
    [Parameter(Mandatory = $true)][string]$AppElf,
    [string]$RunDirectory = ''
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'jlink-common.ps1')

$protocol = Join-Path $PSScriptRoot 'p2_1_protocol.py'
$controlHeader = Join-Path $script:P1RepoRoot 'Libraries\OTA\ota_p2_1_test.h'
$qspiHeader = Join-Path $script:P1RepoRoot 'Libraries\USB_MSC\msc_diskio.h'
$controlSize = Get-P1LiteralMacro -Path $controlHeader -Name 'OTA_P2_1_CONTROL_SIZE'
$controlAddress = (Get-P1LayoutMacro 'OTA_RAM_ORIGIN') +
    (Get-P1LayoutMacro 'OTA_RAM_LENGTH') - $controlSize
$commandMagic = Get-P1LiteralMacro -Path $controlHeader -Name 'OTA_P2_1_COMMAND_MAGIC'
$bootAddress = Get-P1LayoutMacro 'OTA_BOOT_ORIGIN'
$appAddress = Get-P1LayoutMacro 'OTA_APP_ORIGIN'
$stagingOffset = Get-P1LayoutMacro 'OTA_EXT_STAGING'
$slotHeaderSize = Get-P1LayoutMacro 'OTA_SLOT_HEADER_SIZE'
$qspiText = Get-Content -LiteralPath $qspiHeader -Raw
$qspiMatch = [regex]::Match(
    $qspiText,
    '(?m)^\s*#define\s+QSPI1_MEM_BASE\s+(0x[0-9A-Fa-f]+)\b')
if (-not $qspiMatch.Success) {
    throw "QSPI1_MEM_BASE is absent from $qspiHeader"
}
$qspiBase = [Convert]::ToUInt32($qspiMatch.Groups[1].Value.Substring(2), 16)
$stagingXip = $qspiBase + $stagingOffset
$payloadXip = $stagingXip + $slotHeaderSize

function Assert-P21NoJLinkProcess {
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

function Stop-P21JLinkClients {
    foreach ($name in @('JLinkRTTLogger', 'JLinkRTTViewer', 'JLinkGUIServer')) {
        Stop-Process -Name $name -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Milliseconds 300
    Assert-P21NoJLinkProcess
}

function Invoke-P21JLink {
    param(
        [Parameter(Mandatory = $true)][string[]]$Lines,
        [Parameter(Mandatory = $true)][string]$Label,
        [int]$TimeoutSeconds = 120
    )

    Assert-P21NoJLinkProcess
    $commandFile = Join-Path $RunDirectory ($Label + '.jlink')
    $logPath = Join-Path $RunDirectory ($Label + '.log')
    Write-P1JLinkCommandFile -Path $commandFile -Lines $Lines
    try {
        Invoke-P1JLink -CommandFile $commandFile -LogPath $logPath `
            -TimeoutSeconds $TimeoutSeconds | Out-Null
    }
    finally {
        Stop-Process -Name 'JLinkGUIServer' -Force -ErrorAction SilentlyContinue
        Start-Sleep -Milliseconds 300
        Assert-P21NoJLinkProcess
    }
    return $logPath
}

function Get-P21Nm {
    $known = 'D:\singlechip\gcc+gdb+openocd\tools\arm-gnu-toolchain-13.3.rel1-ming\bin\arm-none-eabi-nm.exe'
    if (Test-Path -LiteralPath $known -PathType Leaf) {
        return $known
    }
    return (Get-Command arm-none-eabi-nm.exe -ErrorAction Stop).Source
}

function Get-P21SymbolAddress {
    param(
        [Parameter(Mandatory = $true)][string]$Elf,
        [Parameter(Mandatory = $true)][string]$Name
    )

    $lines = @(& (Get-P21Nm) -an $Elf | Where-Object {
        $_ -match ('^([0-9A-Fa-f]{8})\s+[A-Za-z]\s+' + [regex]::Escape($Name) + '$')
    })
    if ($LASTEXITCODE -ne 0 -or $lines.Count -ne 1) {
        throw "Expected exactly one ELF symbol: $Name"
    }
    $null = $lines[0] -match '^([0-9A-Fa-f]{8})\s+'
    return [Convert]::ToUInt32($Matches[1], 16)
}

function Invoke-P21Protocol {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)

    & (Get-P1Python) $protocol @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "P2-1 protocol tool failed: $($Arguments -join ' ')"
    }
}

foreach ($path in @($BootBin, $AppBin, $AppElf, $protocol)) {
    Assert-P1File $path
}
$BootBin = (Resolve-Path $BootBin).Path
$AppBin = (Resolve-Path $AppBin).Path
$AppElf = (Resolve-Path $AppElf).Path

if ([string]::IsNullOrWhiteSpace($RunDirectory)) {
    $RunDirectory = Join-Path $script:P1RepoRoot `
        ('.cache\p2-1-hardware-evidence-{0:yyyyMMdd-HHmmss}' -f (Get-Date))
}
$RunDirectory = [System.IO.Path]::GetFullPath($RunDirectory)
if (Test-Path -LiteralPath $RunDirectory) {
    throw "P2-1 evidence directory already exists: $RunDirectory"
}
[System.IO.Directory]::CreateDirectory($RunDirectory) | Out-Null

$checkpointSymbol = Get-P21SymbolAddress -Elf $AppElf `
    -Name 'HAL_OTA_StagingEvidenceCheckpoint'
$doneSymbol = Get-P21SymbolAddress -Elf $AppElf `
    -Name 'HAL_OTA_StagingEvidenceDone'

$stagedControl = Join-Path $RunDirectory 'control-staged.bin'
$committedControl = Join-Path $RunDirectory 'control-committed.bin'
$magicPath = Join-Path $RunDirectory 'control-magic.txt'
$metadataPath = Join-Path $RunDirectory 'control-metadata.json'
Invoke-P21Protocol @(
    'command', '--output', $stagedControl,
    '--committed-output', $committedControl,
    '--magic-output', $magicPath,
    '--metadata-output', $metadataPath
)

$stagedBytes = [System.IO.File]::ReadAllBytes($stagedControl)
if ($stagedBytes.Length -ne $controlSize -or
    [BitConverter]::ToUInt32($stagedBytes, 0) -ne 0) {
    throw 'Generated staged control block is invalid'
}
$magicText = (Get-Content -LiteralPath $magicPath -Raw).Trim()
$generatedMagic = [Convert]::ToUInt32($magicText.Substring(2), 16)
if ($generatedMagic -ne $commandMagic) {
    throw 'Generated P2-1 command magic does not match the firmware header'
}

$commandReadback = Join-Path $RunDirectory 'control-command-readback.bin'
$checkpointControl = Join-Path $RunDirectory 'control-checkpoint.bin'
$finalControl = Join-Path $RunDirectory 'control-final.bin'
$checkpointHeader = Join-Path $RunDirectory 'staging-header-checkpoint.bin'
$finalHeader = Join-Path $RunDirectory 'staging-header-final.bin'
$checkpointPayload = Join-Path $RunDirectory 'staging-payload-checkpoint.bin'
$finalPayload = Join-Path $RunDirectory 'staging-payload-final.bin'

Stop-P21JLinkClients
try {
    $flashLog = Invoke-P21JLink -Label 'flash-test-boot-app' -TimeoutSeconds 240 `
        -Lines @(
            'h',
            ('loadbin "{0}", 0x{1:X8}' -f $BootBin, $bootAddress),
            ('verifybin "{0}", 0x{1:X8}' -f $BootBin, $bootAddress),
            ('loadbin "{0}", 0x{1:X8}' -f $AppBin, $appAddress),
            ('verifybin "{0}", 0x{1:X8}' -f $AppBin, $appAddress),
            'qc'
        )
    $flashText = Get-Content -LiteralPath $flashLog -Raw
    if ([regex]::Matches($flashText, 'Verify successful\.').Count -ne 2) {
        throw "Test firmware flash did not report two successful verifies: $flashLog"
    }

    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add('h')
    for ($offset = 4; $offset -lt $stagedBytes.Length; $offset += 4) {
        $value = [BitConverter]::ToUInt32($stagedBytes, $offset)
        $lines.Add(('w4 0x{0:X8}, 0x{1:X8}' -f
                    ($controlAddress + $offset), $value))
    }
    $lines.Add(('w4 0x{0:X8}, 0x{1:X8}' -f
                $controlAddress, $commandMagic))
    $lines.Add(('savebin "{0}", 0x{1:X8}, 0x{2:X}' -f
                $commandReadback, $controlAddress, $controlSize))
    $lines.Add(('SetBP 0x{0:X8}' -f $checkpointSymbol))
    $lines.Add('r')
    $lines.Add('g')
    $lines.Add('WaitHalt 180000')
    $lines.Add('regs')
    $lines.Add('mem32 0xE000ED08, 1')
    $lines.Add('mem32 0xE000ED28, 1')
    $lines.Add(('savebin "{0}", 0x{1:X8}, 0x{2:X}' -f
                $checkpointControl, $controlAddress, $controlSize))
    $lines.Add(('savebin "{0}", 0x{1:X8}, 0x1000' -f
                $checkpointHeader, $stagingXip))
    $lines.Add(('savebin "{0}", 0x{1:X8}, 0x1000' -f
                $checkpointPayload, $payloadXip))
    $lines.Add('ClrBP 1')
    $lines.Add(('SetBP 0x{0:X8}' -f $doneSymbol))
    $lines.Add('r')
    $lines.Add('g')
    $lines.Add('WaitHalt 180000')
    $lines.Add('regs')
    $lines.Add('mem32 0xE000ED08, 1')
    $lines.Add('mem32 0xE000ED28, 1')
    $lines.Add(('savebin "{0}", 0x{1:X8}, 0x{2:X}' -f
                $finalControl, $controlAddress, $controlSize))
    $lines.Add(('savebin "{0}", 0x{1:X8}, 0x1000' -f
                $finalHeader, $stagingXip))
    $lines.Add(('savebin "{0}", 0x{1:X8}, 0x1000' -f
                $finalPayload, $payloadXip))
    $lines.Add('qc')

    $evidenceLog = Invoke-P21JLink -Lines $lines.ToArray() `
        -Label 'staging-reset-reentry' -TimeoutSeconds 420
    $evidenceText = Get-Content -LiteralPath $evidenceLog -Raw
    if ($evidenceText -match 'Could not clear breakpoint' -or
        $evidenceText -notmatch ('Breakpoint set @ addr 0x{0:X8} \(Handle =\s*1\)' -f
                                 $checkpointSymbol) -or
        $evidenceText -notmatch ('PC\s*=\s*{0:X8}\b' -f $checkpointSymbol) -or
        $evidenceText -notmatch ('PC\s*=\s*{0:X8}\b' -f $doneSymbol) -or
        [regex]::Matches($evidenceText, 'CPU halted\.').Count -ne 2) {
        throw "J-Link breakpoint trajectory is invalid: $evidenceLog"
    }

    $expectedHash = (Get-FileHash -LiteralPath $committedControl `
        -Algorithm SHA256).Hash
    $readbackHash = (Get-FileHash -LiteralPath $commandReadback `
        -Algorithm SHA256).Hash
    if ($expectedHash -ne $readbackHash) {
        throw 'Magic-last control block readback does not match the generated command'
    }

    $verifyOutput = Join-Path $RunDirectory 'verification.json'
    $extractDirectory = Join-Path $RunDirectory 'extracted'
    Invoke-P21Protocol @(
        'verify', '--command', $committedControl,
        '--command-readback', $commandReadback,
        '--checkpoint-control', $checkpointControl,
        '--final-control', $finalControl,
        '--checkpoint-header', $checkpointHeader,
        '--final-header', $finalHeader,
        '--checkpoint-payload', $checkpointPayload,
        '--final-payload', $finalPayload,
        '--target-vcode', '20800',
        '--output-dir', $extractDirectory,
        '--output', $verifyOutput
    )
    $verification = Get-Content -LiteralPath $verifyOutput -Raw | ConvertFrom-Json
    if ([string]$verification.result -ne 'PASS') {
        throw "P2-1 binary verification did not pass: $verifyOutput"
    }

    $artifactDirectory = Join-Path $RunDirectory 'firmware'
    [System.IO.Directory]::CreateDirectory($artifactDirectory) | Out-Null
    Copy-Item -LiteralPath $BootBin -Destination `
        (Join-Path $artifactDirectory 'X-Track-Boot.bin')
    Copy-Item -LiteralPath $AppBin -Destination `
        (Join-Path $artifactDirectory 'X-Track-App-GCC.finalized.bin')
    Copy-Item -LiteralPath $AppElf -Destination `
        (Join-Path $artifactDirectory 'X-Track-App-GCC.elf')

    $summary = [ordered]@{
        result = 'PASS'
        control_address = ('0x{0:X8}' -f $controlAddress)
        checkpoint_symbol = ('0x{0:X8}' -f $checkpointSymbol)
        done_symbol = ('0x{0:X8}' -f $doneSymbol)
        staging_xip = ('0x{0:X8}' -f $stagingXip)
        payload_xip = ('0x{0:X8}' -f $payloadXip)
        checks = [int]$verification.checks
        session_sha256 = [string]$verification.session_sha256
        payload_crc32 = [string]$verification.payload_crc32
        payload_sha256 = [string]$verification.payload_sha256
        flash_log = $flashLog
        evidence_log = $evidenceLog
        verification = $verifyOutput
    }
    $summaryPath = Join-Path $RunDirectory 'summary.json'
    [System.IO.File]::WriteAllText(
        $summaryPath,
        ($summary | ConvertTo-Json -Depth 6) + [Environment]::NewLine,
        [System.Text.UTF8Encoding]::new($false))

    $manifestPath = Join-Path $RunDirectory 'sha256-manifest.txt'
    Get-ChildItem -LiteralPath $RunDirectory -File -Recurse |
        Where-Object { $_.FullName -ne $manifestPath } |
        Sort-Object FullName |
        Get-FileHash -Algorithm SHA256 |
        ForEach-Object { '{0}  {1}' -f $_.Hash.ToLowerInvariant(), $_.Path } |
        Set-Content -LiteralPath $manifestPath -Encoding ASCII

    Write-Output ("P2_1_HARDWARE=PASS checks={0} run_directory={1}" -f
        $verification.checks, $RunDirectory)
}
finally {
    Stop-P21JLinkClients
}
