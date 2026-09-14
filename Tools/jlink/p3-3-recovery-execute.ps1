# P3-3 BCB recovery executed-round entry (plan v5, authorization
# P3-3-EXEC-AUTH-20260913 section 3). One phase per invocation, each with
# host-side fail-closed assertions; no automatic retry and no ALL mode.
# Phases: S1A S1B S2 S3 S4 S5 S6. Phase ordering is enforced through the
# <Phase>-result.json chain written into the shared RunDirectory.
#
# Quota alignment (plan v5 section 7): 10 command sessions (S1a 1 + S1b 1
# + S2 2 + S3 2 + S4 1 + S5 2 + S6 1), 2 RTT loggers (S4/S6, 120 s each),
# 6 resets, plus up to 2 reserved RTT signature sessions (S4/S6). The FR4
# fallback consumes S5 (replacement, not addition).

param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('S1A', 'S1B', 'S2', 'S3', 'S4', 'S5', 'S6')]
    [string]$Phase,

    [Parameter(Mandatory = $true)]
    [string]$RunDirectory,

    # Production boot bin from the MAIN worktree build (board identity
    # anchor; the admission worktree has no firmware build).
    [string]$ProductionBootBin = 'D:\github\my\E-Track\MDK-ARM_F435\cmake-generated\build-gcc-release\boot\X-Track-Boot.bin',

    [string]$TestBootHex = '',
    [string]$TestBootBin = '',

    # Production App map from the MAIN worktree build (RTT address source
    # for the on-board App 3.2.0).
    [string]$ProductionAppMap = 'D:\github\my\E-Track\MDK-ARM_F435\cmake-generated\build-gcc-release\app-gcc\X-Track-App-GCC.map',

    [int]$RttTimeoutSeconds = 120,

    # In-session wait after g in the S4/S6 minimal reset sessions so the
    # App boot self-report lands in the RTT up buffer before the logger
    # attaches (single-debugger mutual exclusion: the logger can only
    # start after the J-Link session exits).
    [int]$AppStartWaitMilliseconds = 8000,

    [string]$RttTargetLine = 'OTA: BCB already CONFIRMED vcode=30200',

    # Expected on-board App raw SHA-256 (hex, 64 chars) from the board
    # identification round. When non-empty the S5 app snapshot must match.
    [string]$ExpectedAppSha256 = '',

    # Round-2 adaptation (2026-09-14 incident recovery): the on-board BCB
    # is ROLLBACK(30200) after the unfinalized-image flash, not the round-1
    # CONFIRMED(20801) blocked state. Baseline expectations are therefore
    # parameters; the defaults keep the round-1 semantics.
    [uint32]$BaselineCurVcode = 20801,

    # -1 = record the S2 state without asserting it (round-1 semantics);
    # any value >= 0 additionally asserts the baseline state byte.
    [int]$BaselineState = -1,

    # 'App' = round-1 semantics: the test boot jumps into the App partition
    # and Assert-P1NormalResetEvidence applies. 'BootWait' = round-2
    # semantics: BCB=ROLLBACK with both external slots invalid keeps the
    # test boot in the physical recovery wait loop, so the post-reset PC
    # must be inside the boot region with CFSR=0 (same session shape as
    # Invoke-P16OrdinaryResetEvidence, boot-region assertion inline).
    [ValidateSet('App', 'BootWait')]
    [string]$S1BExpectedPcRegion = 'App'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'p1-6-common.ps1')

if ([string]::IsNullOrWhiteSpace($TestBootHex)) {
    $TestBootHex = Join-Path $script:P1RepoRoot '.cache\p3-3-recovery-boot\boot\X-Track-Boot.hex'
}
if ([string]::IsNullOrWhiteSpace($TestBootBin)) {
    $TestBootBin = Join-Path $script:P1RepoRoot '.cache\p3-3-recovery-boot\boot\X-Track-Boot.bin'
}

$P33TestBootHexSha256 = '409D4F1690B80F5E5B3CE8169119BDD462DEA87A60822C104693C5E8C216CBB4'
$P33TestBootHexLength = 52727
$P33TestBootBinLength = 18720
$P33ProductionBootBinLength = 14724
$P33HexLastAddress = [uint32]0x0800491F
$P33FinalCurVcode = [uint32]30200
$P33ArbiterA = [uint32]1
$P33ArbiterB = [uint32]2
$P33ArbiterNone = [uint32]0
$P33AppResultValid = [uint32]1

function Write-P33PhaseResult {
    param(
        [Parameter(Mandatory = $true)][string]$PhaseName,
        [Parameter(Mandatory = $true)]$Record
    )
    Write-P16Json -Value $Record -Path (Join-Path $RunDirectory ($PhaseName + '-result.json'))
}

function Assert-P33PriorPhase {
    param(
        [Parameter(Mandatory = $true)][string]$Prior,
        [string[]]$AcceptResults = @('PASS')
    )
    $path = Join-Path $RunDirectory ($Prior + '-result.json')
    Assert-P1File $path
    $record = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
    if ($record.result -notin $AcceptResults) {
        throw ('Prior phase {0} result is {1} (accepted: {2})' -f
            $Prior, $record.result, ($AcceptResults -join '/'))
    }
    return $record
}

function Get-P33HexEraseLog {
    param([Parameter(Mandatory = $true)][string]$LogPath)
    # Preserve the flash/erase related log lines verbatim for independent
    # review; the parsed sector boundary assertion is done separately via
    # the flashed readback bytes (stronger than log text).
    $lines = @(Get-Content -LiteralPath $LogPath | Where-Object {
        $_ -match 'Eras|Download|Program|Verify|O\.K\.|FAILED'
    })
    return ($lines -join [Environment]::NewLine)
}

function Get-P33Sha256Hex {
    param([Parameter(Mandatory = $true)][string]$Path)
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Write-P33RawHexToFile {
    param(
        [Parameter(Mandatory = $true)][string]$Hex,
        [Parameter(Mandatory = $true)][string]$Path
    )
    if ($Hex.Length % 2 -ne 0) {
        throw 'Raw hex string has an odd length'
    }
    $bytes = New-Object byte[] ($Hex.Length / 2)
    for ($i = 0; $i -lt $bytes.Length; $i++) {
        $bytes[$i] = [Convert]::ToByte($Hex.Substring($i * 2, 2), 16)
    }
    [System.IO.File]::WriteAllBytes($Path, $bytes)
    return $bytes.Length
}

function Get-P33RttText {
    param([Parameter(Mandatory = $true)][string]$Path)
    $bytes = [System.IO.File]::ReadAllBytes($Path)
    return [System.Text.Encoding]::ASCII.GetString($bytes)
}

function Invoke-P33MinimalResetSession {
    param(
        [Parameter(Mandatory = $true)][string]$Label
    )
    # Minimal reset session (plan v5 section 3): r, g, in-session wait, qc.
    # No halt and no regs - the wait lets the App boot self-report land in
    # the RTT up buffer; the logger attaches only after this session exits.
    $lines = @(
        'r',
        'g',
        ('Sleep {0}' -f $AppStartWaitMilliseconds),
        'qc'
    )
    return Invoke-P16JLink -Lines $lines -RunDirectory $RunDirectory `
        -Label $Label -TimeoutSeconds ([Math]::Ceiling($AppStartWaitMilliseconds / 1000.0) + 120)
}

function Invoke-P33RttEvidence {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][bool]$FailIsFr4
    )
    # Reserved signature session (mem8 only; no write, no reset) then the
    # single logger for this label (120 s hard timeout by default).
    $rttAddress = Get-P1MapRttAddress -MapPath $ProductionAppMap
    Test-P1RttSignature -Address $rttAddress -RunDirectory $RunDirectory `
        -Label ($Label + '-rtt-signature') | Out-Null
    $rttOut = Join-Path $RunDirectory ($Label + '-rtt.log')
    # Out-Null keeps the function's return value a single result object:
    # Invoke-P1RttCapture emits a status line into the pipeline, which
    # would otherwise make callers receive an Object[] and break strict
    # property access ($rtt.LogPath) in S4/S6.
    Invoke-P1RttCapture -Address $rttAddress -OutputPath $rttOut `
        -TimeoutSeconds $RttTimeoutSeconds | Out-Null
    $text = Get-P33RttText -Path $rttOut
    if ($text -notmatch [regex]::Escape($RttTargetLine)) {
        if ($FailIsFr4) {
            # FR4 path (plan v5 section 6): record the miss, then fail.
            # S5 accepts S4 with result FR4_MISSING_LINE and runs as the
            # fallback session (replacement for REC5, same form).
            Write-P33PhaseResult -PhaseName $Label -Record ([ordered]@{
                result       = 'FR4_MISSING_LINE'
                rtt_address  = ('0x{0:X8}' -f $rttAddress)
                rtt_log      = $rttOut
                target_line  = $RttTargetLine
            })
        }
        throw ('RTT target line not found in {0} (FR4/FR6): {1}' -f
            $rttOut, $RttTargetLine)
    }
    return [pscustomobject]@{
        Address = $rttAddress
        LogPath = $rttOut
        Text = $text
    }
}

switch ($Phase) {
    'S1A' {
        # REC0 + REC1 flash + RAM invalidate in ONE halted connection
        # (plan v5 section 2.3). The test boot never runs inside S1A.
        if (Test-Path -LiteralPath $RunDirectory) {
            throw "S1A requires a fresh RunDirectory: $RunDirectory"
        }
        Assert-P1File $ProductionBootBin
        if ((Get-Item -LiteralPath $ProductionBootBin).Length -ne $P33ProductionBootBinLength) {
            throw ('Production boot bin size mismatch: {0}' -f $ProductionBootBin)
        }
        Assert-P1File $TestBootHex
        if ((Get-Item -LiteralPath $TestBootHex).Length -ne $P33TestBootHexLength) {
            throw ('Test boot HEX size mismatch: {0}' -f $TestBootHex)
        }
        $hexSha = Get-P33Sha256Hex -Path $TestBootHex
        if ($hexSha -ne $P33TestBootHexSha256.ToLowerInvariant()) {
            throw ('Test boot HEX SHA-256 mismatch: {0}' -f $hexSha)
        }
        Assert-P1File $TestBootBin
        if ((Get-Item -LiteralPath $TestBootBin).Length -ne $P33TestBootBinLength) {
            throw ('Test boot bin size mismatch: {0}' -f $TestBootBin)
        }
        # Independent HEX record range parse (offline T17 method).
        $hexLast = [uint32]0
        $extBase = [uint32]0
        foreach ($line in [System.IO.File]::ReadLines($TestBootHex)) {
            if ($line.Length -lt 11) { continue }
            $n = [Convert]::ToUInt32($line.Substring(1, 2), 16)
            $a = [Convert]::ToUInt32($line.Substring(3, 4), 16)
            $t = [Convert]::ToUInt32($line.Substring(7, 2), 16)
            if ($t -eq 4 -and $n -eq 2) {
                $extBase = [Convert]::ToUInt32($line.Substring(9, 4), 16) -shl 16
            }
            elseif ($t -eq 0 -and $n -gt 0) {
                $end = $extBase + $a + $n - 1
                if ($end -gt $hexLast) { $hexLast = [uint32]$end }
            }
        }
        if ($hexLast -ne $P33HexLastAddress) {
            throw ('Test boot HEX range changed: last data end 0x{0:X8}' -f $hexLast)
        }
        $sectorTop = ($hexLast -band (-bnot 0xFFF)) + 0xFFF
        if ($sectorTop -ne ($script:P16BootRegionBase + $script:P16BootAffectedLength - 1)) {
            throw ('Test boot HEX sector top exceeds the affected region: 0x{0:X8}' -f $sectorTop)
        }

        [System.IO.Directory]::CreateDirectory($RunDirectory) | Out-Null
        # Bind the production bin identity into the round directory.
        $roundProdBin = Join-Path $RunDirectory 'production-boot.bin'
        Copy-Item -LiteralPath $ProductionBootBin -Destination $roundProdBin
        if ((Get-Item -LiteralPath $roundProdBin).Length -ne $P33ProductionBootBinLength) {
            throw 'Round production boot copy size mismatch'
        }

        $backupBin = Join-Path $RunDirectory 'boot-region-backup.bin'
        $flashed = Join-Path $RunDirectory 's1a-flashed-readback.bin'
        $invalidate = Join-Path $RunDirectory 's1a-invalidate-readback.bin'
        $lines = @(
            'h',
            ('savebin "{0}", 0x{1:X8}, 0x{2:X}' -f
                $backupBin, $script:P16BootRegionBase, $script:P16BootAffectedLength),
            ('loadfile "{0}"' -f (Resolve-Path $TestBootHex).Path),
            ('savebin "{0}", 0x{1:X8}, 0x{2:X}' -f
                $flashed, $script:P16BootRegionBase, $script:P16BootAffectedLength),
            ('w4 0x{0:X8}, 0x00000000' -f $script:P16ControlAddress),
            ('savebin "{0}", 0x{1:X8}, 0x{2:X}' -f
                $invalidate, $script:P16ControlAddress, $script:P16ControlSize),
            'qc'
        )
        # Command order is guaranteed by the CommandFile sequence plus
        # -ExitOnError 1: a failed savebin backup stops loadfile.
        $log = Invoke-P16JLink -Lines $lines -RunDirectory $RunDirectory `
            -Label 'S1A' -TimeoutSeconds 300

        # REC0 assertions.
        Assert-P1File $backupBin
        if ((Get-Item -LiteralPath $backupBin).Length -ne [int64]$script:P16BootAffectedLength) {
            throw 'Boot region backup size mismatch'
        }
        $prefixLen = Assert-P16BootBackupMatchesProduction `
            -BackupBin $backupBin -ProductionBootBin $roundProdBin
        if ($prefixLen -ne $P33ProductionBootBinLength) {
            throw ('Backup anchor prefix length mismatch: {0}' -f $prefixLen)
        }
        $backupBytes = [System.IO.File]::ReadAllBytes($backupBin)
        $tailStream = [System.IO.MemoryStream]::new()
        $tailStream.Write($backupBytes, $P33ProductionBootBinLength,
            $backupBytes.Length - $P33ProductionBootBinLength)
        $tailStream.Position = 0
        $tailSha = (Get-FileHash -InputStream $tailStream -Algorithm SHA256).Hash.ToLowerInvariant()
        $fullSha = Get-P33Sha256Hex -Path $backupBin

        # REC1 assertions: flashed region equals the test boot bin, and the
        # erased tail inside the affected region reads 0xFF.
        Assert-P1File $flashed
        $flashedBytes = [System.IO.File]::ReadAllBytes($flashed)
        if ($flashedBytes.Length -ne [int64]$script:P16BootAffectedLength) {
            throw 'Flashed readback size mismatch'
        }
        $testBytes = [System.IO.File]::ReadAllBytes($TestBootBin)
        for ($i = 0; $i -lt $testBytes.Length; $i++) {
            if ($flashedBytes[$i] -ne $testBytes[$i]) {
                throw ('Flashed readback differs from test boot bin at offset {0}' -f $i)
            }
        }
        for ($i = $testBytes.Length; $i -lt $flashedBytes.Length; $i++) {
            if ($flashedBytes[$i] -ne 0xFF) {
                throw ('Erased tail is not 0xFF at offset {0}' -f $i)
            }
        }

        # RAM invalidate happened BEFORE the first reset (plan v5 fix l).
        Assert-P1File $invalidate
        $null = Test-P16InvalidatedControl -Path $invalidate

        $record = [ordered]@{
            result = 'PASS'
            backup = $backupBin
            backup_sha256 = $fullSha
            backup_tail_sha256 = $tailSha
            backup_tail_bytes = $backupBytes.Length - $P33ProductionBootBinLength
            production_bin = $roundProdBin
            production_bin_sha256 = (Get-P33Sha256Hex -Path $roundProdBin)
            test_boot_hex = $TestBootHex
            test_boot_hex_sha256 = $hexSha
            test_boot_hex_last_address = ('0x{0:X8}' -f $hexLast)
            flashed_readback = $flashed
            flashed_readback_sha256 = (Get-P33Sha256Hex -Path $flashed)
            invalidate_readback = $invalidate
            flash_log = $log
            flash_log_erase_excerpt = (Get-P33HexEraseLog -LogPath $log)
        }
        Write-P33PhaseResult -PhaseName 'S1A' -Record $record
        Write-Output ('S1A_RESULT=PASS backup_sha256={0} tail_sha256={1}' -f
            $fullSha, $tailSha)
        Write-Output ('S1A_FLASH=PASS test_boot_verified=1 erased_tail_ff=1 ram_magic_zero=1')
    }

    'S1B' {
        # REC1 reset 1: first start of the test boot with the control
        # block already invalidated and verified inside S1A.
        Assert-P33PriorPhase -Prior 'S1A' | Out-Null
        if ($S1BExpectedPcRegion -eq 'App') {
            $evidence = Invoke-P16OrdinaryResetEvidence -RunDirectory $RunDirectory `
                -Label 'S1B-reset1' -WaitMilliseconds 5000
        }
        else {
            # BootWait mode (round-2): BCB=ROLLBACK and both external
            # slots are invalid, so the test boot must be parked in the
            # physical recovery wait loop. Same session shape as
            # Invoke-P16OrdinaryResetEvidence; the assertion is inline so
            # the shared library keeps its App-partition semantics.
            $log = Invoke-P16JLink -Lines @(
                'r', 'g', 'Sleep 5000', 'h', 'regs',
                'mem32 0xE000ED08, 1',
                'mem32 0xE000ED28, 1',
                'g', 'qc'
            ) -RunDirectory $RunDirectory -Label 'S1B-reset1' `
                -TimeoutSeconds 80
            $logText = Get-Content -LiteralPath $log -Raw
            $pc = Get-P1LogHex32 -Text $logText `
                -Pattern '^\s*PC\s*=\s*(?:0x)?([0-9A-Fa-f]{8})\b' -Label 'PC'
            $vtor = Get-P1LogHex32 -Text $logText `
                -Pattern '^\s*E000ED08\s*=\s*(?:0x)?([0-9A-Fa-f]{8})\b' -Label 'VTOR'
            $cfsr = Get-P1LogHex32 -Text $logText `
                -Pattern '^\s*E000ED28\s*=\s*(?:0x)?([0-9A-Fa-f]{8})\b' -Label 'CFSR'
            $bootEnd = [uint64]$script:P16BootRegionBase +
                [uint64]$script:P16BootAffectedLength
            if ([uint64]$pc -lt [uint64]$script:P16BootRegionBase -or
                [uint64]$pc -ge $bootEnd) {
                throw ('S1B boot-wait PC is outside the boot region: 0x{0:X8}' -f $pc)
            }
            if ($cfsr -ne 0) {
                throw ('S1B boot-wait CFSR is nonzero: 0x{0:X8}' -f $cfsr)
            }
            # VTOR is recorded but not asserted: the test boot parks in a
            # delay loop and its VTOR is boot-owned, not part of the
            # recovery contract.
            $evidence = [pscustomobject]@{
                pc = ('0x{0:X8}' -f $pc)
                vtor = ('0x{0:X8}' -f $vtor)
                cfsr = ('0x{0:X8}' -f $cfsr)
                log = $log
            }
        }
        Write-P33PhaseResult -PhaseName 'S1B' -Record ([ordered]@{
            result = 'PASS'
            expected_pc_region = $S1BExpectedPcRegion
            pc = $evidence.pc
            vtor = $evidence.vtor
            cfsr = $evidence.cfsr
            log = $evidence.log
        })
        Write-Output ('S1B_RESULT=PASS region={0} pc={1} vtor={2} cfsr={3}' -f
            $S1BExpectedPcRegion, $evidence.pc, $evidence.vtor, $evidence.cfsr)
    }

    'S2' {
        # REC2 baseline SNAPSHOT, BCB only (arg0=0 no QSPI, arg1=1 BCB_ONLY).
        # Two sessions (invalidate gate + command) and reset 2 are inside
        # Invoke-P16Command.
        Assert-P33PriorPhase -Prior 'S1B' | Out-Null
        $run = Invoke-P16Command -Opcode $script:P16OpcodeSnapshot `
            -Arg0 0 -Arg1 $script:P16SnapshotBcbOnly `
            -RunDirectory $RunDirectory -Label 'S2-snapshot-baseline'
        $active = [uint32]$run.Result.active
        if ($active -ne $P33ArbiterA -and $active -ne $P33ArbiterB) {
            throw ('S2 baseline arbiter is not A/B: {0}' -f $active)
        }
        if ([uint32]$run.Result.cur_vcode -ne $BaselineCurVcode) {
            throw ('S2 baseline cur_vcode mismatch: {0} (expected {1})' -f
                $run.Result.cur_vcode, $BaselineCurVcode)
        }
        if ($BaselineState -ge 0 -and [int][uint32]$run.Result.state -ne $BaselineState) {
            throw ('S2 baseline state mismatch: {0} (expected {1})' -f
                [uint32]$run.Result.state, $BaselineState)
        }
        # Mandatory BCB raw preservation (authorization: no trimming).
        # Each arbiter block is BCB_SIZE=64 bytes (eeprom_bcb.h:26,
        # snapshot_bcb raw_a[BCB_SIZE]), so a hex string is 128 chars.
        $rawA = [string]$run.Result.bcb_a_raw
        $rawB = [string]$run.Result.bcb_b_raw
        if ($rawA.Length -ne 128 -or $rawB.Length -ne 128) {
            throw ('S2 BCB raw length mismatch: A={0} B={1}' -f
                $rawA.Length, $rawB.Length)
        }
        $rawAPath = Join-Path $RunDirectory 's2-bcb-a-raw.bin'
        $rawBPath = Join-Path $RunDirectory 's2-bcb-b-raw.bin'
        $null = Write-P33RawHexToFile -Hex $rawA -Path $rawAPath
        $null = Write-P33RawHexToFile -Hex $rawB -Path $rawBPath
        Write-P33PhaseResult -PhaseName 'S2' -Record ([ordered]@{
            result = 'PASS'
            active = $active
            cur_vcode = [uint32]$run.Result.cur_vcode
            state = [uint32]$run.Result.state
            seq = [uint32]$run.Result.seq
            bcb_a_raw = $rawAPath
            bcb_a_raw_sha256 = (Get-P33Sha256Hex -Path $rawAPath)
            bcb_b_raw = $rawBPath
            bcb_b_raw_sha256 = (Get-P33Sha256Hex -Path $rawBPath)
            result_bin = $run.ResultBin
            log = $run.Log
        })
        Write-Output ('S2_RESULT=PASS active={0} cur_vcode={1} bcb_a={2} bcb_b={3}' -f
            $active, [uint32]$run.Result.cur_vcode,
            (Get-P33Sha256Hex -Path $rawAPath), (Get-P33Sha256Hex -Path $rawBPath))
    }

    'S3' {
        # REC3 CLEAR_BCB: the only persistent BCB erase (EEPROM 0x00-0x7F
        # written to 0xFF by firmware code). detail failures map to
        # plan v5 FR3/FR3b.
        Assert-P33PriorPhase -Prior 'S2' | Out-Null
        $run = Invoke-P16Command -Opcode $script:P16OpcodeClearBcb `
            -RunDirectory $RunDirectory -Label 'S3-clear-bcb'
        $active = [uint32]$run.Result.active
        if ($active -ne $P33ArbiterNone) {
            throw ('S3 post-clear arbiter is not NONE: {0}' -f $active)
        }
        $rawA = [string]$run.Result.bcb_a_raw
        $rawB = [string]$run.Result.bcb_b_raw
        # 64 bytes per block (BCB_SIZE, eeprom_bcb.h:26) = 128 hex chars.
        if ($rawA -notmatch '^[fF]{128}$' -or $rawB -notmatch '^[fF]{128}$') {
            throw 'S3 BCB raw blocks are not all 0xFF after CLEAR_BCB'
        }
        Write-P33PhaseResult -PhaseName 'S3' -Record ([ordered]@{
            result = 'PASS'
            active = $active
            bcb_a_all_ff = $true
            bcb_b_all_ff = $true
            result_bin = $run.ResultBin
            log = $run.Log
        })
        Write-Output ('S3_RESULT=PASS active={0} bcb_a_ff=1 bcb_b_ff=1' -f $active)
    }

    'S4' {
        # REC4: explicit reset 4 triggers the NONE->commit_confirmed(30200)
        # rebuild, then the reserved RTT signature session and the single
        # logger capture the App boot self-report.
        Assert-P33PriorPhase -Prior 'S3' | Out-Null
        $null = Invoke-P33MinimalResetSession -Label 'S4-reset4'
        $rtt = Invoke-P33RttEvidence -Label 'S4' -FailIsFr4 $true
        Write-P33PhaseResult -PhaseName 'S4' -Record ([ordered]@{
            result = 'PASS'
            rtt_address = ('0x{0:X8}' -f $rtt.Address)
            rtt_log = $rtt.LogPath
            rtt_log_sha256 = (Get-P33Sha256Hex -Path $rtt.LogPath)
            target_line = $RttTargetLine
        })
        Write-Output ('S4_RESULT=PASS rtt=0x{0:X8} line_found=1' -f $rtt.Address)
    }

    'S5' {
        # REC5 final SNAPSHOT including the internal App snapshot
        # (arg0=0 no QSPI, arg1=0 app snapshot). When S4 recorded
        # FR4_MISSING_LINE this invocation IS the FR4 fallback session
        # (replacement for REC5 - plan v5 fix k).
        $priorS4 = Assert-P33PriorPhase -Prior 'S4' `
            -AcceptResults @('PASS', 'FR4_MISSING_LINE')
        $invokedAsFallback = ($priorS4.result -eq 'FR4_MISSING_LINE')
        $run = Invoke-P16Command -Opcode $script:P16OpcodeSnapshot `
            -Arg0 0 -Arg1 0 `
            -RunDirectory $RunDirectory -Label 'S5-snapshot-final'
        $active = [uint32]$run.Result.active
        if ($active -ne $P33ArbiterA -and $active -ne $P33ArbiterB) {
            throw ('S5 final arbiter is not A/B: {0}' -f $active)
        }
        if ([uint32]$run.Result.cur_vcode -ne $P33FinalCurVcode) {
            throw ('S5 final cur_vcode mismatch: {0}' -f $run.Result.cur_vcode)
        }
        if ([uint32]$run.Result.seq -ne 0) {
            throw ('S5 final seq is not zero: {0}' -f $run.Result.seq)
        }
        if ([uint32]$run.Result.app_result -ne $P33AppResultValid) {
            throw ('S5 app snapshot is not VALID: {0}' -f $run.Result.app_result)
        }
        if ([uint32]$run.Result.app_vcode -ne $P33FinalCurVcode) {
            throw ('S5 app_vcode mismatch: {0}' -f $run.Result.app_vcode)
        }
        $appSha = [string]$run.Result.app_sha256
        if ($appSha.Length -ne 64) {
            throw ('S5 app_sha256 length mismatch: {0}' -f $appSha.Length)
        }
        if (-not [string]::IsNullOrWhiteSpace($ExpectedAppSha256) -and
            $appSha.ToLowerInvariant() -ne $ExpectedAppSha256.ToLowerInvariant()) {
            throw ('S5 app_sha256 mismatch: {0} (expected {1})' -f
                $appSha, $ExpectedAppSha256)
        }
        Write-P33PhaseResult -PhaseName 'S5' -Record ([ordered]@{
            result = 'PASS'
            invoked_as_fr4_fallback = $invokedAsFallback
            active = $active
            cur_vcode = [uint32]$run.Result.cur_vcode
            state = [uint32]$run.Result.state
            seq = [uint32]$run.Result.seq
            app_result = [uint32]$run.Result.app_result
            app_vcode = [uint32]$run.Result.app_vcode
            app_len = [uint32]$run.Result.app_len
            app_sha256 = $appSha
            app_sha256_checked = (-not [string]::IsNullOrWhiteSpace($ExpectedAppSha256))
            result_bin = $run.ResultBin
            log = $run.Log
        })
        Write-Output ('S5_RESULT=PASS fallback={0} active={1} cur_vcode={2} seq={3} app_vcode={4} app_sha256={5}' -f
            $invokedAsFallback, $active, [uint32]$run.Result.cur_vcode,
            [uint32]$run.Result.seq, [uint32]$run.Result.app_vcode, $appSha)
    }

    'S6' {
        # REC6 full-region Boot restore from the S1A backup (loadbin +
        # verifybin + full-region readback SHA equality inside
        # Invoke-P16BootRegionRestore), then reset 6 and the REC7 RTT
        # final evidence from the production App.
        Assert-P33PriorPhase -Prior 'S5' | Out-Null
        $backupBin = Join-Path $RunDirectory 'boot-region-backup.bin'
        Assert-P1File $backupBin
        $restore = Invoke-P16BootRegionRestore -BackupBin $backupBin `
            -RunDirectory $RunDirectory -Label 'S6-boot-restore'
        $null = Invoke-P33MinimalResetSession -Label 'S6-reset6'
        $rtt = Invoke-P33RttEvidence -Label 'S6' -FailIsFr4 $false
        Write-P33PhaseResult -PhaseName 'S6' -Record ([ordered]@{
            result = 'PASS'
            restored_sha256 = $restore.Sha256
            restore_readback = $restore.Readback
            restore_log = $restore.Log
            rtt_address = ('0x{0:X8}' -f $rtt.Address)
            rtt_log = $rtt.LogPath
            rtt_log_sha256 = (Get-P33Sha256Hex -Path $rtt.LogPath)
            target_line = $RttTargetLine
        })
        Write-Output ('S6_RESULT=PASS restored_sha256={0} rtt=0x{1:X8} line_found=1' -f
            $restore.Sha256, $rtt.Address)
    }
}
