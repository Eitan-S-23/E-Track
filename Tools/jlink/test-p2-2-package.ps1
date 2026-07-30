[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$TestBootBin,
    [Parameter(Mandatory = $true)][string]$TestAppBin,
    [Parameter(Mandatory = $true)][string]$TestAppElf,
    [Parameter(Mandatory = $true)][string]$ProductionBootBin,
    [Parameter(Mandatory = $true)][string]$ProductionAppBin,
    [Parameter(Mandatory = $true)][string]$ProductionAppElf,
    [Parameter(Mandatory = $true)][string]$GoldenPackage,
    [Parameter(Mandatory = $true)][string]$GoldenImage,
    [string]$RunDirectory = ''
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'jlink-common.ps1')

$protocol = Join-Path $PSScriptRoot 'p2_2_protocol.py'
$controlHeader = Join-Path $script:P1RepoRoot 'Libraries\OTA\ota_p2_2_test.h'
$qspiHeader = Join-Path $script:P1RepoRoot 'Libraries\USB_MSC\msc_diskio.h'
$controlSize = Get-P1LiteralMacro -Path $controlHeader -Name 'OTA_P2_2_CONTROL_SIZE'
$packageOffset = Get-P1LiteralMacro -Path $controlHeader -Name 'OTA_P2_2_PACKAGE_OFFSET'
$controlAddress = (Get-P1LayoutMacro 'OTA_RAM_ORIGIN') +
    (Get-P1LayoutMacro 'OTA_RAM_LENGTH') - $controlSize
$commandMagic = Get-P1LiteralMacro -Path $controlHeader -Name 'OTA_P2_2_COMMAND_MAGIC'
$bootAddress = Get-P1LayoutMacro 'OTA_BOOT_ORIGIN'
$appAddress = Get-P1LayoutMacro 'OTA_APP_ORIGIN'
$appLength = Get-P1LayoutMacro 'OTA_APP_LENGTH'
$candidateOffset = Get-P1LayoutMacro 'OTA_EXT_CANDIDATE'
$slotHeaderSize = Get-P1LayoutMacro 'OTA_SLOT_HEADER_SIZE'
$qspiText = Get-Content -LiteralPath $qspiHeader -Raw
$qspiMatch = [regex]::Match(
    $qspiText,
    '(?m)^\s*#define\s+QSPI1_MEM_BASE\s+(0x[0-9A-Fa-f]+)\b')
if (-not $qspiMatch.Success) {
    throw "QSPI1_MEM_BASE is absent from $qspiHeader"
}
$qspiBase = [Convert]::ToUInt32($qspiMatch.Groups[1].Value.Substring(2), 16)
$candidateHeaderXip = $qspiBase + $candidateOffset
$candidateImageXip = $candidateHeaderXip + $slotHeaderSize

function Assert-P22NoJLinkProcess {
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

function Stop-P22JLinkClients {
    foreach ($name in @('JLinkRTTLogger', 'JLinkRTTViewer', 'JLinkGUIServer')) {
        Stop-Process -Name $name -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Milliseconds 300
    Assert-P22NoJLinkProcess
}

function Invoke-P22JLink {
    param(
        [Parameter(Mandatory = $true)][string[]]$Lines,
        [Parameter(Mandatory = $true)][string]$Label,
        [int]$TimeoutSeconds = 180
    )

    Assert-P22NoJLinkProcess
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
        Assert-P22NoJLinkProcess
    }
    return $logPath
}

function Get-P22Nm {
    $known = 'D:\singlechip\gcc+gdb+openocd\tools\arm-gnu-toolchain-13.3.rel1-ming\bin\arm-none-eabi-nm.exe'
    if (Test-Path -LiteralPath $known -PathType Leaf) {
        return $known
    }
    return (Get-Command arm-none-eabi-nm.exe -ErrorAction Stop).Source
}

function Get-P22SymbolAddress {
    param(
        [Parameter(Mandatory = $true)][string]$Elf,
        [Parameter(Mandatory = $true)][string]$Name
    )

    $lines = @(& (Get-P22Nm) -an $Elf | Where-Object {
        $_ -match ('^([0-9A-Fa-f]{8})\s+[A-Za-z]\s+' + [regex]::Escape($Name) + '$')
    })
    if ($LASTEXITCODE -ne 0 -or $lines.Count -ne 1) {
        throw "Expected exactly one ELF symbol: $Name"
    }
    $null = $lines[0] -match '^([0-9A-Fa-f]{8})\s+'
    return [Convert]::ToUInt32($Matches[1], 16)
}

function Invoke-P22Protocol {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)

    & (Get-P1Python) $protocol @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "P2-2 protocol tool failed: $($Arguments -join ' ')"
    }
}

function Get-P22WriteBlockLines {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][uint32]$Address
    )

    $bytes = [System.IO.File]::ReadAllBytes($Path)
    if ($bytes.Length -ne $controlSize -or ($bytes.Length % 4) -ne 0) {
        throw "Control block size is invalid for word writes: $Path"
    }
    $lines = New-Object System.Collections.Generic.List[string]
    for ($offset = 0; $offset -lt $bytes.Length; $offset += 4) {
        $value = [BitConverter]::ToUInt32($bytes, $offset)
        $lines.Add(('w4 0x{0:X8}, 0x{1:X8}' -f
                    ($Address + $offset), $value))
    }
    return $lines.ToArray()
}

function Restore-P22Production {
    param([uint32]$RttAddress)

    $flashLog = Invoke-P22JLink -Label 'restore-production-flash' `
        -TimeoutSeconds 240 -Lines @(
            'h',
            ('loadbin "{0}", 0x{1:X8}' -f $ProductionBootBin, $bootAddress),
            ('verifybin "{0}", 0x{1:X8}' -f $ProductionBootBin, $bootAddress),
            ('loadbin "{0}", 0x{1:X8}' -f $ProductionAppBin, $appAddress),
            ('verifybin "{0}", 0x{1:X8}' -f $ProductionAppBin, $appAddress),
            'qc'
        )
    $flashText = Get-Content -LiteralPath $flashLog -Raw
    if ([regex]::Matches($flashText, 'Verify successful\.').Count -ne 2) {
        throw "Production restore did not report two successful verifies: $flashLog"
    }

    $diagLog = Invoke-P22JLink -Label 'restore-production-diagnostic' `
        -TimeoutSeconds 90 -Lines @(
            'r',
            'g',
            'Sleep 30000',
            'h',
            'regs',
            'mem32 0xE000ED08, 1',
            'mem32 0xE000ED28, 1',
            ('mem8 0x{0:X8}, 16' -f $RttAddress),
            'g',
            'qc'
        )
    $diagText = Get-Content -LiteralPath $diagLog -Raw
    $pcMatch = [regex]::Match($diagText, '(?im)^\s*PC\s*=\s*([0-9A-Fa-f]{8})\b')
    if (-not $pcMatch.Success) {
        throw "Production diagnostic has no PC: $diagLog"
    }
    $pc = [Convert]::ToUInt32($pcMatch.Groups[1].Value, 16)
    if ($pc -lt $appAddress -or $pc -ge $appAddress + $appLength -or
        $diagText -notmatch '(?is)E000ED08.*?08010000' -or
        $diagText -notmatch '(?is)E000ED28.*?00000000' -or
        $diagText -notmatch '53 45 47 47 45 52 20 52 54 54') {
        throw "Production App/VTOR/CFSR/RTT verification failed: $diagLog"
    }
    return [ordered]@{
        flash_log = $flashLog
        diagnostic_log = $diagLog
        pc = ('0x{0:X8}' -f $pc)
        rtt_address = ('0x{0:X8}' -f $RttAddress)
    }
}

foreach ($path in @(
        $TestBootBin, $TestAppBin, $TestAppElf,
        $ProductionBootBin, $ProductionAppBin, $ProductionAppElf,
        $GoldenPackage, $GoldenImage, $protocol)) {
    Assert-P1File $path
}
$TestBootBin = (Resolve-Path $TestBootBin).Path
$TestAppBin = (Resolve-Path $TestAppBin).Path
$TestAppElf = (Resolve-Path $TestAppElf).Path
$ProductionBootBin = (Resolve-Path $ProductionBootBin).Path
$ProductionAppBin = (Resolve-Path $ProductionAppBin).Path
$ProductionAppElf = (Resolve-Path $ProductionAppElf).Path
$GoldenPackage = (Resolve-Path $GoldenPackage).Path
$GoldenImage = (Resolve-Path $GoldenImage).Path

if ([string]::IsNullOrWhiteSpace($RunDirectory)) {
    $RunDirectory = Join-Path $script:P1RepoRoot `
        ('.cache\p2-2-hardware-evidence-{0:yyyyMMdd-HHmmss}' -f (Get-Date))
}
$RunDirectory = [System.IO.Path]::GetFullPath($RunDirectory)
if (Test-Path -LiteralPath $RunDirectory) {
    throw "P2-2 evidence directory already exists: $RunDirectory"
}
[System.IO.Directory]::CreateDirectory($RunDirectory) | Out-Null

$doneSymbol = Get-P22SymbolAddress -Elf $TestAppElf `
    -Name 'HAL_OTA_PackageEvidenceDone'
$readySymbol = Get-P22SymbolAddress -Elf $TestAppElf `
    -Name 'HAL_OTA_PackageEvidenceReady'
$rttAddress = Get-P22SymbolAddress -Elf $ProductionAppElf -Name '_SEGGER_RTT'
$cases = @('success', 'bad-header-crc', 'bad-payload', 'equal-version')
$caseSummaries = New-Object System.Collections.Generic.List[object]
$bcbSha256 = $null
$testFailure = $null
$restoreSummary = $null

Stop-P22JLinkClients
try {
    try {
        $flashLog = Invoke-P22JLink -Label 'flash-test-boot-app' `
            -TimeoutSeconds 240 -Lines @(
                'h',
                ('loadbin "{0}", 0x{1:X8}' -f $TestBootBin, $bootAddress),
                ('verifybin "{0}", 0x{1:X8}' -f $TestBootBin, $bootAddress),
                ('loadbin "{0}", 0x{1:X8}' -f $TestAppBin, $appAddress),
                ('verifybin "{0}", 0x{1:X8}' -f $TestAppBin, $appAddress),
                'qc'
            )
        $flashText = Get-Content -LiteralPath $flashLog -Raw
        if ([regex]::Matches($flashText, 'Verify successful\.').Count -ne 2) {
            throw "Test firmware flash did not report two successful verifies: $flashLog"
        }

        foreach ($case in $cases) {
            $caseDirectory = Join-Path $RunDirectory $case
            [System.IO.Directory]::CreateDirectory($caseDirectory) | Out-Null
            $stagedControl = Join-Path $caseDirectory 'control-staged.bin'
            $committedControl = Join-Path $caseDirectory 'control-committed.bin'
            $magicPath = Join-Path $caseDirectory 'control-magic.txt'
            $metadataPath = Join-Path $caseDirectory 'control-metadata.json'
            Invoke-P22Protocol @(
                'command', '--case', $case, '--package', $GoldenPackage,
                '--output', $stagedControl,
                '--committed-output', $committedControl,
                '--magic-output', $magicPath,
                '--metadata-output', $metadataPath
            )
            $magicText = (Get-Content -LiteralPath $magicPath -Raw).Trim()
            $generatedMagic = [Convert]::ToUInt32($magicText.Substring(2), 16)
            if ($generatedMagic -ne $commandMagic) {
                throw "Generated command magic mismatch for $case"
            }

            $commandReadback = Join-Path $caseDirectory 'control-command-readback.bin'
            $finalControl = Join-Path $caseDirectory 'control-final.bin'
            $headerBefore = Join-Path $caseDirectory 'candidate-header-before.bin'
            $headerAfter = Join-Path $caseDirectory 'candidate-header-after.bin'
            $imageBefore = Join-Path $caseDirectory 'candidate-image-before.bin'
            $imageAfter = Join-Path $caseDirectory 'candidate-image-after.bin'
            $caseLines = @(
                'h',
                ('SetBP 0x{0:X8}' -f $readySymbol),
                'r',
                'g',
                'WaitHalt 60000',
                'regs',
                ('savebin "{0}", 0x{1:X8}, 0x1000' -f
                    $headerBefore, $candidateHeaderXip),
                ('savebin "{0}", 0x{1:X8}, 0x1000' -f
                    $imageBefore, $candidateImageXip)
            )
            $caseLines += Get-P22WriteBlockLines -Path $stagedControl `
                -Address $controlAddress
            $caseLines += @(
                ('w4 0x{0:X8}, 0x{1:X8}' -f $controlAddress, $commandMagic),
                ('savebin "{0}", 0x{1:X8}, 0x{2:X}' -f
                    $commandReadback, $controlAddress, $controlSize),
                ('SetBP 0x{0:X8}' -f $doneSymbol),
                'g',
                'WaitHalt 180000',
                'regs',
                'mem32 0xE000ED08, 1',
                'mem32 0xE000ED28, 1',
                ('savebin "{0}", 0x{1:X8}, 0x{2:X}' -f
                    $finalControl, $controlAddress, $controlSize),
                ('savebin "{0}", 0x{1:X8}, 0x1000' -f
                    $headerAfter, $candidateHeaderXip),
                ('savebin "{0}", 0x{1:X8}, 0x1000' -f
                    $imageAfter, $candidateImageXip),
                'qc'
            )
            $caseLog = Invoke-P22JLink -Label ("case-{0}" -f $case) `
                -TimeoutSeconds 360 -Lines $caseLines
            $caseText = Get-Content -LiteralPath $caseLog -Raw
            $trajectoryPattern = '(?is)PC\s*=\s*{0:X8}\b.*PC\s*=\s*{1:X8}\b' -f
                $readySymbol, $doneSymbol
            if ($caseText -notmatch $trajectoryPattern -or
                $caseText -notmatch '(?is)E000ED08.*?08010000' -or
                $caseText -notmatch '(?is)E000ED28.*?00000000') {
                throw "J-Link trajectory is invalid for ${case}: $caseLog"
            }

            $expectedHash = (Get-FileHash -LiteralPath $committedControl `
                -Algorithm SHA256).Hash
            $readbackHash = (Get-FileHash -LiteralPath $commandReadback `
                -Algorithm SHA256).Hash
            if ($expectedHash -ne $readbackHash) {
                throw "Magic-last command readback mismatch for $case"
            }

            $verifyOutput = Join-Path $caseDirectory 'verification.json'
            $extractDirectory = Join-Path $caseDirectory 'extracted'
            Invoke-P22Protocol @(
                'verify', '--case', $case,
                '--command', $committedControl,
                '--command-readback', $commandReadback,
                '--final-control', $finalControl,
                '--candidate-header-before', $headerBefore,
                '--candidate-header-after', $headerAfter,
                '--candidate-image-before', $imageBefore,
                '--candidate-image-after', $imageAfter,
                '--expected-image', $GoldenImage,
                '--extract-dir', $extractDirectory,
                '--output', $verifyOutput
            )
            $verification = Get-Content -LiteralPath $verifyOutput -Raw |
                ConvertFrom-Json
            if ([string]$verification.result -ne 'PASS') {
                throw "Binary verification did not pass for $case"
            }
            $caseSummaries.Add([ordered]@{
                case = $case
                checks = [int]$verification.checks
                expected_result = [int]$verification.expected_result
                actual_result = [int]$verification.actual_result
                package_sha256 = [string]$verification.package_sha256
                candidate_before_sha256 = [string]$verification.candidate_before_sha256
                candidate_after_sha256 = [string]$verification.candidate_after_sha256
                bcb_sha256 = [string]$verification.bcb_sha256
                workspace_peak = [int]$verification.workspace_peak
                log = $caseLog
                verification = $verifyOutput
            })
        }

        $bcbHashes = @($caseSummaries | ForEach-Object {
            [string]$_['bcb_sha256']
        } | Sort-Object -Unique)
        if ($bcbHashes.Count -ne 1) {
            throw "BCB snapshots differ across P2-2 cases: $($bcbHashes -join ', ')"
        }
        $bcbSha256 = $bcbHashes[0]
    }
    catch {
        $testFailure = $_
    }

    try {
        $restoreSummary = Restore-P22Production -RttAddress $rttAddress
    }
    catch {
        if ($null -ne $testFailure) {
            throw "P2-2 test failed: $($testFailure.Exception.Message); production restore also failed: $($_.Exception.Message)"
        }
        throw
    }

    if ($null -ne $testFailure) {
        throw $testFailure
    }

    $artifactDirectory = Join-Path $RunDirectory 'firmware'
    [System.IO.Directory]::CreateDirectory($artifactDirectory) | Out-Null
    Copy-Item -LiteralPath $TestBootBin -Destination `
        (Join-Path $artifactDirectory 'test-X-Track-Boot.bin')
    Copy-Item -LiteralPath $TestAppBin -Destination `
        (Join-Path $artifactDirectory 'test-X-Track-App-GCC.finalized.bin')
    Copy-Item -LiteralPath $TestAppElf -Destination `
        (Join-Path $artifactDirectory 'test-X-Track-App-GCC.elf')
    Copy-Item -LiteralPath $ProductionBootBin -Destination `
        (Join-Path $artifactDirectory 'production-X-Track-Boot.bin')
    Copy-Item -LiteralPath $ProductionAppBin -Destination `
        (Join-Path $artifactDirectory 'production-X-Track-App-GCC.finalized.bin')
    Copy-Item -LiteralPath $ProductionAppElf -Destination `
        (Join-Path $artifactDirectory 'production-X-Track-App-GCC.elf')

    $totalChecks = 0
    foreach ($caseSummary in $caseSummaries) {
        $totalChecks += [int]$caseSummary['checks']
    }
    $summary = [ordered]@{
        result = 'PASS'
        cases = $caseSummaries.Count
        checks = [int]$totalChecks
        control_address = ('0x{0:X8}' -f $controlAddress)
        control_size = $controlSize
        package_offset = $packageOffset
        ready_symbol = ('0x{0:X8}' -f $readySymbol)
        done_symbol = ('0x{0:X8}' -f $doneSymbol)
        candidate_header_xip = ('0x{0:X8}' -f $candidateHeaderXip)
        candidate_image_xip = ('0x{0:X8}' -f $candidateImageXip)
        bcb_sha256 = $bcbSha256
        cases_detail = $caseSummaries
        production_restore = $restoreSummary
    }
    $summaryPath = Join-Path $RunDirectory 'summary.json'
    [System.IO.File]::WriteAllText(
        $summaryPath,
        ($summary | ConvertTo-Json -Depth 8) + [Environment]::NewLine,
        [System.Text.UTF8Encoding]::new($false))

    $manifestPath = Join-Path $RunDirectory 'sha256-manifest.txt'
    Get-ChildItem -LiteralPath $RunDirectory -File -Recurse |
        Where-Object { $_.FullName -ne $manifestPath } |
        Sort-Object FullName |
        Get-FileHash -Algorithm SHA256 |
        ForEach-Object { '{0}  {1}' -f $_.Hash.ToLowerInvariant(), $_.Path } |
        Set-Content -LiteralPath $manifestPath -Encoding ASCII

    Write-Output ("P2_2_HARDWARE=PASS cases={0} checks={1} run_directory={2}" -f
        $caseSummaries.Count, $totalChecks, $RunDirectory)
}
finally {
    Stop-P22JLinkClients
}
