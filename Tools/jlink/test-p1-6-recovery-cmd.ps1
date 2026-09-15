# P3-3 recovery command offline verification (2026-09-13, ruling round 4).
# Scope: reuse the pure functions in Tools/jlink/p1-6-common.ps1 to verify,
# with no device access and no J-Link process:
#   1. CLEAR_BCB / SNAPSHOT command block generation + decode round trip
#   2. ARM checkpoint block generation + decode round trip
#   3. staged/committed commit ordering semantics (magic-zero staging)
#   4. Get-P16WordWriteLines generated J-Link script shape (text only,
#      never executed here)
#   5. fail-closed tamper rejection (CRC, inverse fields, magic, size)
#   6. RAM commit-ordering defect reproduction: a stale same-kind magic
#      plus a fresh body parses as valid control BEFORE the final magic
#      write (T12) - the defect the 2026-09-13 ruling replayed offline
#   7. fixed-sequence interruption sweep: with the invalidate-first gate
#      (Get-P16InvalidateLines + Test-P16InvalidatedControl), every write
#      interruption point between "magic zeroed" and "magic committed"
#      parses as invalid control; only "before the invalidate write"
#      (complete old state, known) and "after the final magic write"
#      (complete new command) are valid (T13/T13b)
#   8. invalidate gate fail-closed: a zero-magic readback passes, any
#      command/arm/done block is rejected (T15)
#   9. Boot region recovery scope: the affected flash region is bound to
#      0x08000000..0x08004FFF (0x5000) from the REAL test-boot artifacts
#      (bin 18720 B, HEX last record 0x0800491F -> 4 KB sector 4), the
#      production boot bin is 14724 B (NOT 16384), the backup anchor
#      asserts the backup prefix equals the production bin byte-for-byte,
#      the tail (5756 B) is unknown content that must be restored
#      verbatim (never assumed 0xFF), and the restore script rewrites
#      exactly the affected sectors with a full-region readback hash
#      check (T16/T16b/T17)
# All outputs stay inside <repo>/.cache/p3-3-recovery-boot/cmd-verify/.

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
. (Join-Path $repoRoot 'Tools\jlink\p1-6-common.ps1')

$runDir = Join-Path $repoRoot '.cache\p3-3-recovery-boot\cmd-verify'
if (Test-Path -LiteralPath $runDir) {
    throw "Run directory already exists (refusing to overwrite): $runDir"
}
[System.IO.Directory]::CreateDirectory($runDir) | Out-Null

$script:Passed = 0
$script:Failed = 0
function Write-VerifyResult {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][bool]$Ok,
        [string]$Detail = ''
    )
    if ($Ok) { $script:Passed++ } else { $script:Failed++ }
    if ($Detail -ne '') {
        Write-Output ('{0} {1} {2}' -f ($(if ($Ok) { 'PASS' } else { 'FAIL' })), $Name, $Detail)
    }
    else {
        Write-Output ('{0} {1}' -f ($(if ($Ok) { 'PASS' } else { 'FAIL' })), $Name)
    }
}

function Copy-TamperedBlock {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination,
        [Parameter(Mandatory = $true)][int]$ByteOffset,
        [Parameter(Mandatory = $true)][int]$XorMask
    )
    $bytes = [System.IO.File]::ReadAllBytes($Source)
    $bytes[$ByteOffset] = $bytes[$ByteOffset] -bxor $XorMask
    [System.IO.File]::WriteAllBytes($Destination, $bytes)
}

$headerPath = Join-Path $repoRoot 'Libraries\OTA\ota_p1_6_test.h'
$offMagic = Get-P1LiteralMacro -Path $headerPath -Name 'OTA_P1_6_OFF_MAGIC'
$offOpcode = Get-P1LiteralMacro -Path $headerPath -Name 'OTA_P1_6_OFF_OPCODE'
$offArg0 = Get-P1LiteralMacro -Path $headerPath -Name 'OTA_P1_6_OFF_ARG0'
$offCommandCrc = Get-P1LiteralMacro -Path $headerPath -Name 'OTA_P1_6_OFF_COMMAND_CRC32'
$offTargetCp = Get-P1LiteralMacro -Path $headerPath -Name 'OTA_P1_6_OFF_TARGET_CHECKPOINT'
$controlSize = Get-P1LiteralMacro -Path $headerPath -Name 'OTA_P1_6_CONTROL_SIZE'
$p16Version = Get-P1LiteralMacro -Path $headerPath -Name 'OTA_P1_6_VERSION'

Write-Output ('control_address=0x{0:X8} control_size={1}' -f $script:P16ControlAddress, $controlSize)
Write-Output ('magic_command=0x{0:X8} magic_arm=0x{1:X8} magic_done=0x{2:X8}' -f $script:P16MagicCommand, $script:P16MagicArm, $script:P16MagicDone)

# --- T1: CLEAR_BCB command block generation + decode round trip ---
$clear = New-P16EncodedBlock -Kind Command -RunDirectory $runDir -Label 'clear-bcb' -Opcode $script:P16OpcodeClearBcb
$d = Get-P16DecodedControl -Path $clear.Committed
$ok = ($d.kind -eq 'command') -and
    ([uint32]$d.magic -eq $script:P16MagicCommand) -and
    ([uint32]$d.version -eq $p16Version) -and
    ([uint32]$d.opcode -eq $script:P16OpcodeClearBcb) -and
    ([bool]$d.opcode_inverse_valid) -and ([bool]$d.cookie_inverse_valid) -and
    ([bool]$d.command_crc_valid) -and ([bool]$d.command_valid) -and
    (-not [bool]$d.arm_valid) -and (-not [bool]$d.done)
Write-VerifyResult -Name 'T1 clear_bcb round trip' -Ok $ok -Detail ("opcode={0}" -f $d.opcode)

# --- T2: SNAPSHOT command block with non-zero args ---
$snap = New-P16EncodedBlock -Kind Command -RunDirectory $runDir -Label 'snapshot' -Opcode $script:P16OpcodeSnapshot -Arg0 $script:P16SnapshotBcbOnly -Arg1 0x12345678 -Arg2 0 -Arg3 0x5A5A5A5A
$d2 = Get-P16DecodedControl -Path $snap.Committed
$ok = ([uint32]$d2.opcode -eq $script:P16OpcodeSnapshot) -and
    ([uint32]$d2.arg0 -eq $script:P16SnapshotBcbOnly) -and
    ([uint32]$d2.arg1 -eq 0x12345678) -and
    ([uint32]$d2.arg2 -eq 0) -and
    ([uint32]$d2.arg3 -eq 0x5A5A5A5A) -and
    ([bool]$d2.command_valid)
Write-VerifyResult -Name 'T2 snapshot args round trip' -Ok $ok

# --- T3: ARM checkpoint block generation + decode round trip ---
$arm = New-P16EncodedBlock -Kind Arm -RunDirectory $runDir -Label 'arm-cp' -Checkpoint 7 -Arg0 0x11111111 -Arg1 0x22222222
$d3 = Get-P16DecodedControl -Path $arm.Committed
$ok = ($d3.kind -eq 'arm') -and
    ([uint32]$d3.magic -eq $script:P16MagicArm) -and
    ([uint32]$d3.status -eq $script:P16StatusArmed) -and
    ([uint32]$d3.target_checkpoint -eq 7) -and
    ([uint32]$d3.target_arg0 -eq 0x11111111) -and
    ([uint32]$d3.target_arg1 -eq 0x22222222) -and
    ([bool]$d3.target_crc_valid) -and ([bool]$d3.arm_valid) -and
    (-not [bool]$d3.command_valid)
Write-VerifyResult -Name 'T3 arm checkpoint round trip' -Ok $ok

# --- T4: staged/committed blocks differ only in the magic word ---
$sb = [System.IO.File]::ReadAllBytes($clear.Staged)
$cb = [System.IO.File]::ReadAllBytes($clear.Committed)
$diffOffsets = @(for ($i = 0; $i -lt $controlSize; $i++) {
    if ($sb[$i] -ne $cb[$i]) { $i }
})
$onlyMagic = ($diffOffsets.Count -eq 4) -and
    ($diffOffsets[0] -eq $offMagic) -and ($diffOffsets[3] -eq ($offMagic + 3)) -and
    ([BitConverter]::ToUInt32($sb, $offMagic) -eq 0)
Write-VerifyResult -Name 'T4 staged keeps magic zero' -Ok $onlyMagic -Detail ("diff_bytes={0}" -f $diffOffsets.Count)

$ds = Get-P16DecodedControl -Path $clear.Staged
$ok = ($ds.kind -eq 'unknown') -and (-not [bool]$ds.command_valid) -and
    (-not [bool]$ds.arm_valid) -and (-not [bool]$ds.done)
Write-VerifyResult -Name 'T4b staged block is not valid control' -Ok $ok

# --- T5: Get-P16WordWriteLines emits the J-Link script text (not executed) ---
$readbackPath = Join-Path $runDir 'planned-readback.bin'
$lines = Get-P16WordWriteLines -StagedBlock $clear.Staged -Magic $clear.Magic -ReadbackPath $readbackPath
$bodyCount = [int](($controlSize - 4) / 4)
$expectedTotal = 1 + $bodyCount + 3
$ok = ($lines.Count -eq $expectedTotal) -and
    ($lines[0] -eq 'h') -and ($lines[$lines.Count - 1] -eq 'qc') -and
    ($lines[1] -eq ('w4 0x{0:X8}, 0x{1:X8}' -f ($script:P16ControlAddress + 4), [BitConverter]::ToUInt32($sb, 4))) -and
    ($lines[1 + $bodyCount] -eq ('w4 0x{0:X8}, 0x{1:X8}' -f $script:P16ControlAddress, $clear.Magic)) -and
    ($lines[2 + $bodyCount] -eq ('savebin "{0}", 0x{1:X8}, 0x{2:X}' -f $readbackPath, $script:P16ControlAddress, $controlSize))
Write-VerifyResult -Name 'T5 word write lines shape' -Ok $ok -Detail ("lines={0}" -f $lines.Count)

$rejected = $false
try {
    Get-P16WordWriteLines -StagedBlock $clear.Committed -Magic $clear.Magic -ReadbackPath $readbackPath | Out-Null
}
catch {
    $rejected = $true
}
Write-VerifyResult -Name 'T5b nonzero-magic staged rejected' -Ok $rejected

# --- T6: tamper an arg0 byte -> command CRC must reject ---
$tamperPath = Join-Path $runDir 'tamper-arg0.bin'
Copy-TamperedBlock -Source $clear.Committed -Destination $tamperPath -ByteOffset $offArg0 -XorMask 1
$dt = Get-P16DecodedControl -Path $tamperPath
$ok = (-not [bool]$dt.command_crc_valid) -and (-not [bool]$dt.command_valid)
Write-VerifyResult -Name 'T6 arg0 tamper rejected' -Ok $ok

# --- T7: tamper opcode without its inverse -> inverse check must reject ---
$tamperPath = Join-Path $runDir 'tamper-opcode.bin'
Copy-TamperedBlock -Source $clear.Committed -Destination $tamperPath -ByteOffset $offOpcode -XorMask 1
$dt = Get-P16DecodedControl -Path $tamperPath
$ok = (-not [bool]$dt.opcode_inverse_valid) -and (-not [bool]$dt.command_valid)
Write-VerifyResult -Name 'T7 opcode tamper rejected' -Ok $ok

# --- T8: tamper the stored command CRC -> must reject ---
$tamperPath = Join-Path $runDir 'tamper-crc.bin'
Copy-TamperedBlock -Source $clear.Committed -Destination $tamperPath -ByteOffset $offCommandCrc -XorMask 1
$dt = Get-P16DecodedControl -Path $tamperPath
$ok = (-not [bool]$dt.command_crc_valid) -and (-not [bool]$dt.command_valid)
Write-VerifyResult -Name 'T8 command crc tamper rejected' -Ok $ok

# --- T9: tamper the arm target checkpoint -> target CRC must reject ---
$tamperPath = Join-Path $runDir 'tamper-target.bin'
Copy-TamperedBlock -Source $arm.Committed -Destination $tamperPath -ByteOffset $offTargetCp -XorMask 1
$dt = Get-P16DecodedControl -Path $tamperPath
$ok = (-not [bool]$dt.target_crc_valid) -and (-not [bool]$dt.arm_valid)
Write-VerifyResult -Name 'T9 arm target tamper rejected' -Ok $ok

# --- T10: rewrite magic to DONE -> recognized as done, not command/arm ---
$doneBlock = [System.IO.File]::ReadAllBytes($clear.Committed)
$doneMagicBytes = [System.BitConverter]::GetBytes([uint32]$script:P16MagicDone)
[System.Array]::Copy($doneMagicBytes, 0, $doneBlock, $offMagic, 4)
$donePath = Join-Path $runDir 'magic-done.bin'
[System.IO.File]::WriteAllBytes($donePath, $doneBlock)
$dt = Get-P16DecodedControl -Path $donePath
$ok = ($dt.kind -eq 'done') -and ([bool]$dt.done) -and
    (-not [bool]$dt.command_valid) -and (-not [bool]$dt.arm_valid)
Write-VerifyResult -Name 'T10 done magic recognized' -Ok $ok

# --- T11: wrong-size input must fail decode (fail-closed) ---
$sourceBytes = [System.IO.File]::ReadAllBytes($clear.Committed)
$shortPath = Join-Path $runDir 'short.bin'
[System.IO.File]::WriteAllBytes($shortPath, $sourceBytes[0..($controlSize - 2)])
$rejectedShort = $false
try { Get-P16DecodedControl -Path $shortPath | Out-Null }
catch { $rejectedShort = $true }

$long = New-Object byte[] ($controlSize + 2)
[System.Array]::Copy($sourceBytes, $long, $controlSize)
$longPath = Join-Path $runDir 'long.bin'
[System.IO.File]::WriteAllBytes($longPath, $long)
$rejectedLong = $false
try { Get-P16DecodedControl -Path $longPath | Out-Null }
catch { $rejectedLong = $true }
Write-VerifyResult -Name 'T11 size guard rejects wrong sizes' -Ok ($rejectedShort -and $rejectedLong)

# --- T12: RAM commit-ordering defect reproduction (2026-09-13 ruling) ---
# A staged file with magic=0 does not prove the on-device RAM magic is 0.
# If the device retains a stale same-kind magic (COMMAND/ARM/DONE), the
# fresh body parses as a valid command BEFORE the final magic write.
$staleBody = [System.IO.File]::ReadAllBytes($clear.Staged)

$mixCmd = [byte[]]::new($controlSize)
[System.Array]::Copy($staleBody, $mixCmd, $controlSize)
[System.Array]::Copy([System.BitConverter]::GetBytes([uint32]$script:P16MagicCommand), 0, $mixCmd, $offMagic, 4)
$mixCmdPath = Join-Path $runDir 'defect-stale-command-magic.bin'
[System.IO.File]::WriteAllBytes($mixCmdPath, $mixCmd)
$dm = Get-P16DecodedControl -Path $mixCmdPath
$okCmd = [bool]$dm.command_valid -and
    ([uint32]$dm.opcode -eq $script:P16OpcodeClearBcb)

$armStagedBytes = [System.IO.File]::ReadAllBytes($arm.Staged)
$mixArm = [byte[]]::new($controlSize)
[System.Array]::Copy($armStagedBytes, $mixArm, $controlSize)
[System.Array]::Copy([System.BitConverter]::GetBytes([uint32]$script:P16MagicArm), 0, $mixArm, $offMagic, 4)
$mixArmPath = Join-Path $runDir 'defect-stale-arm-magic.bin'
[System.IO.File]::WriteAllBytes($mixArmPath, $mixArm)
$da = Get-P16DecodedControl -Path $mixArmPath
$okArm = [bool]$da.arm_valid

$mixDone = [byte[]]::new($controlSize)
[System.Array]::Copy($staleBody, $mixDone, $controlSize)
[System.Array]::Copy([System.BitConverter]::GetBytes([uint32]$script:P16MagicDone), 0, $mixDone, $offMagic, 4)
$mixDonePath = Join-Path $runDir 'defect-stale-done-magic.bin'
[System.IO.File]::WriteAllBytes($mixDonePath, $mixDone)
$dd = Get-P16DecodedControl -Path $mixDonePath
$okDone = [bool]$dd.done
Write-VerifyResult -Name 'T12 defect reproduction (stale magic + fresh body = valid)' -Ok ($okCmd -and $okArm -and $okDone) -Detail ("cmd={0} arm={1} done={2}" -f $okCmd, $okArm, $okDone)

# --- T13: interrupted-write sweep against the FIXED sequence ---
# Fixed sequence: [invalidate w4] -> [readback gate] -> [body w4 x127]
#                 -> [magic w4] -> [savebin]
# Step 0   = interrupted before the invalidate write (complete old state,
#            deterministically known - the only remaining window)
# Step 1   = after the invalidate write (magic zeroed, body untouched)
# Step 1+j = after the j-th body word (j = 1..127)
# Step 129 = after the final magic write (complete new command)
# Every intermediate step MUST parse as invalid control.
function New-P16InterruptedBytes {
    param(
        [Parameter(Mandatory = $true)][byte[]]$Initial,
        [Parameter(Mandatory = $true)][byte[]]$NewStaged,
        [Parameter(Mandatory = $true)][uint32]$NewMagic,
        [Parameter(Mandatory = $true)][int]$Step
    )
    $bytes = [byte[]]::new($Initial.Length)
    [System.Array]::Copy($Initial, $bytes, $Initial.Length)
    if ($Step -ge 1) {
        [System.Array]::Copy([System.BitConverter]::GetBytes([uint32]0), 0, $bytes, 0, 4)
        $bodyWords = [int](($bytes.Length - 4) / 4)
        $toWrite = $Step - 1
        if ($toWrite -gt $bodyWords) { $toWrite = $bodyWords }
        for ($w = 0; $w -lt $toWrite; $w++) {
            $src = 4 + 4 * $w
            [System.Array]::Copy($NewStaged, $src, $bytes, $src, 4)
        }
    }
    if ($Step -ge 129) {
        [System.Array]::Copy([System.BitConverter]::GetBytes($NewMagic), 0, $bytes, 0, 4)
    }
    return $bytes
}

function Test-P16BytesAllInvalid {
    param(
        [Parameter(Mandatory = $true)][byte[]]$Bytes,
        [Parameter(Mandatory = $true)][string]$Path
    )
    [System.IO.File]::WriteAllBytes($Path, $Bytes)
    $d = Get-P16DecodedControl -Path $Path
    return (-not [bool]$d.command_valid) -and
        (-not [bool]$d.arm_valid) -and (-not [bool]$d.done)
}

$garbageInit = [byte[]]::new($controlSize)
for ($i = 0; $i -lt $controlSize; $i += 4) {
    [System.Array]::Copy([System.BitConverter]::GetBytes([uint32]0x5A5A5A5A), 0, $garbageInit, $i, 4)
}

# Sweep 1: COMMAND initial state (worst case), all 130 interruption points.
$oldCommand = [System.IO.File]::ReadAllBytes($snap.Committed)
$newStagedBytes = [System.IO.File]::ReadAllBytes($clear.Staged)
$violations = 0
for ($step = 0; $step -le 129; $step++) {
    $bytes = New-P16InterruptedBytes -Initial $oldCommand `
        -NewStaged $newStagedBytes -NewMagic ([uint32]$clear.Magic) -Step $step
    $p = Join-Path $runDir ('t13-command-step-{0:D3}.bin' -f $step)
    [System.IO.File]::WriteAllBytes($p, $bytes)
    $d = Get-P16DecodedControl -Path $p
    if ($step -eq 0) {
        # complete old command (SNAPSHOT) - known state, no magic/body mix
        if (-not ([bool]$d.command_valid -and
                  [uint32]$d.opcode -eq $script:P16OpcodeSnapshot)) {
            $violations++
        }
    }
    elseif ($step -eq 129) {
        # complete new command (CLEAR_BCB) - the intended target state
        if (-not ([bool]$d.command_valid -and
                  [uint32]$d.opcode -eq $script:P16OpcodeClearBcb)) {
            $violations++
        }
    }
    elseif ((-not [bool]$d.command_valid) -and
            (-not [bool]$d.arm_valid) -and (-not [bool]$d.done)) {
        # invalid as required
    }
    else {
        $violations++
    }
}
Write-VerifyResult -Name 'T13 fixed-sequence interruption sweep (COMMAND, 130 steps)' -Ok ($violations -eq 0) -Detail ("violations={0}" -f $violations)

# Sweep 2: ARM / DONE / garbage initial states, key points {0,1,2,128,129}.
$initialSets = @(
    @{ Label = 'arm';     Bytes = [System.IO.File]::ReadAllBytes($arm.Committed); Step0Valid = $true },
    @{ Label = 'done';    Bytes = [System.IO.File]::ReadAllBytes($donePath);      Step0Valid = $true },
    @{ Label = 'garbage'; Bytes = $garbageInit;                                   Step0Valid = $false }
)
$violations2 = 0
foreach ($set in $initialSets) {
    foreach ($step in @(0, 1, 2, 128, 129)) {
        $bytes = New-P16InterruptedBytes -Initial $set.Bytes `
            -NewStaged $newStagedBytes -NewMagic ([uint32]$clear.Magic) -Step $step
        $p = Join-Path $runDir ('t13-{0}-step-{1:D3}.bin' -f $set.Label, $step)
        [System.IO.File]::WriteAllBytes($p, $bytes)
        $d = Get-P16DecodedControl -Path $p
        if ($step -eq 0) {
            $expectValid = [bool]$set.Step0Valid
            $isOld = if ($set.Label -eq 'arm') { [bool]$d.arm_valid }
                     elseif ($set.Label -eq 'done') { [bool]$d.done }
                     else { $false }
            if ($expectValid -ne $isOld) { $violations2++ }
        }
        elseif ($step -eq 129) {
            if (-not ([bool]$d.command_valid -and
                      [uint32]$d.opcode -eq $script:P16OpcodeClearBcb)) {
                $violations2++
            }
        }
        elseif ((-not [bool]$d.command_valid) -and
                (-not [bool]$d.arm_valid) -and (-not [bool]$d.done)) {
            # invalid as required
        }
        else {
            $violations2++
        }
    }
}
Write-VerifyResult -Name 'T13b interruption sweep (ARM/DONE/garbage initials)' -Ok ($violations2 -eq 0) -Detail ("violations={0}" -f $violations2)

# --- T14: Get-P16InvalidateLines script shape (text only, not executed) ---
$invPath = Join-Path $runDir 'planned-invalidate-readback.bin'
$invLines = Get-P16InvalidateLines -ReadbackPath $invPath
$ok = ($invLines.Count -eq 4) -and
    ($invLines[0] -eq 'h') -and
    ($invLines[1] -eq ('w4 0x{0:X8}, 0x00000000' -f $script:P16ControlAddress)) -and
    ($invLines[2] -eq ('savebin "{0}", 0x{1:X8}, 0x{2:X}' -f $invPath, $script:P16ControlAddress, $controlSize)) -and
    ($invLines[3] -eq 'qc')
Write-VerifyResult -Name 'T14 invalidate lines shape' -Ok $ok -Detail ("lines={0}" -f $invLines.Count)

# --- T15: Test-P16InvalidatedControl is fail-closed ---
$invalAccepted = $false
try {
    $dec = Test-P16InvalidatedControl -Path $clear.Staged
    $invalAccepted = $true
}
catch {
    $invalAccepted = $false
}
$rejectedCommand = $false
try { Test-P16InvalidatedControl -Path $clear.Committed | Out-Null }
catch { $rejectedCommand = $true }
$rejectedArm = $false
try { Test-P16InvalidatedControl -Path $arm.Committed | Out-Null }
catch { $rejectedArm = $true }
$rejectedDone = $false
try { Test-P16InvalidatedControl -Path $donePath | Out-Null }
catch { $rejectedDone = $true }
Write-VerifyResult -Name 'T15 invalidate gate fail-closed' -Ok ($invalAccepted -and $rejectedCommand -and $rejectedArm -and $rejectedDone) -Detail ("ok={0}/{1}/{2}/{3}" -f $invalAccepted, $rejectedCommand, $rejectedArm, $rejectedDone)

# --- T16: Boot region backup anchor (synthetic, function logic only) ---
# Synthetic production reference (14724 B) + synthetic full-region backup
# (20480 B) whose tail is a NON-0xFF pattern: proves the anchor checks the
# prefix only and the tail content is carried verbatim, never assumed 0xFF.
$prodLen = 14724
$tailLen = [int]$script:P16BootAffectedLength - $prodLen
$synthProd = [byte[]]::new($prodLen)
for ($i = 0; $i -lt $prodLen; $i += 4) {
    [System.Array]::Copy([System.BitConverter]::GetBytes([uint32](0x11110000 + $i)), 0, $synthProd, $i, 4)
}
$synthProdPath = Join-Path $runDir 'synth-production-boot.bin'
[System.IO.File]::WriteAllBytes($synthProdPath, $synthProd)

$synthBackup = [byte[]]::new([int]$script:P16BootAffectedLength)
[System.Array]::Copy($synthProd, $synthBackup, $prodLen)
for ($i = $prodLen; $i -lt $synthBackup.Length; $i += 4) {
    [System.Array]::Copy([System.BitConverter]::GetBytes([uint32]0x5A5A5A5A), 0, $synthBackup, $i, 4)
}
$synthBackupPath = Join-Path $runDir 'synth-boot-region-backup.bin'
[System.IO.File]::WriteAllBytes($synthBackupPath, $synthBackup)

$anchorLen = Assert-P16BootBackupMatchesProduction -BackupBin $synthBackupPath -ProductionBootBin $synthProdPath
$ok = ($anchorLen -eq $prodLen)
Write-VerifyResult -Name 'T16 backup anchor accepts matching prefix' -Ok $ok -Detail ("anchor_len={0} tail_len={1}" -f $anchorLen, $tailLen)

# Negative: one flipped prefix byte must be rejected.
$tamperedBackup = [byte[]]::new($synthBackup.Length)
[System.Array]::Copy($synthBackup, $tamperedBackup, $synthBackup.Length)
$tamperedBackup[100] = $tamperedBackup[100] -bxor 1
$tamperedBackupPath = Join-Path $runDir 'synth-boot-region-backup-tampered.bin'
[System.IO.File]::WriteAllBytes($tamperedBackupPath, $tamperedBackup)
$rejectedTamper = $false
try { Assert-P16BootBackupMatchesProduction -BackupBin $tamperedBackupPath -ProductionBootBin $synthProdPath | Out-Null }
catch { $rejectedTamper = $true }

# Negative: a backup shorter than the production bin must be rejected.
$shortBackupPath = Join-Path $runDir 'synth-boot-region-backup-short.bin'
[System.IO.File]::WriteAllBytes($shortBackupPath, $synthProd[0..9999])
$rejectedShortBk = $false
try { Assert-P16BootBackupMatchesProduction -BackupBin $shortBackupPath -ProductionBootBin $synthProdPath | Out-Null }
catch { $rejectedShortBk = $true }
Write-VerifyResult -Name 'T16b backup anchor fail-closed' -Ok ($rejectedTamper -and $rejectedShortBk) -Detail ("tamper={0} short={1}" -f $rejectedTamper, $rejectedShortBk)

# --- T17: affected-region scope bound to the REAL artifacts ---
# The test boot bin under .cache/p3-3-recovery-boot/boot is 18720 B; its HEX
# data records end at 0x0800491F, which lands in 4 KB sector 4, so the
# affected region is 0x08000000..0x08004FFF (0x5000). The constants in
# p1-6-common.ps1 must match this, and the restore script must rewrite
# exactly that region.
$testBootBin = Join-Path $repoRoot '.cache\p3-3-recovery-boot\boot\X-Track-Boot.bin'
$testBootHex = Join-Path $repoRoot '.cache\p3-3-recovery-boot\boot\X-Track-Boot.hex'
$scopeOk = ($script:P16BootRegionBase -eq 0x08000000) -and
    ($script:P16BootAffectedLength -eq 0x5000) -and
    (Test-Path -LiteralPath $testBootBin) -and
    ((Get-Item -LiteralPath $testBootBin).Length -eq 18720)
if ($scopeOk) {
    # Independent HEX parse: max data end address across all records.
    $hexLast = [uint32]0
    $extBase = [uint32]0
    foreach ($line in [System.IO.File]::ReadLines($testBootHex)) {
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
    $sectorTop = ($hexLast -band (-bnot 0xFFF)) + 0xFFF
    $scopeOk = ($hexLast -eq 0x0800491F) -and
        ($sectorTop -eq ($script:P16BootRegionBase + $script:P16BootAffectedLength - 1)) -and
        ($tailLen -eq 5756)
}
$testBootSha = ''
if (Test-Path -LiteralPath $testBootBin) {
    $testBootSha = (Get-FileHash -LiteralPath $testBootBin -Algorithm SHA256).Hash.Substring(0, 16)
}
Write-VerifyResult -Name 'T17 affected region scope (0x08000000..0x08004FFF)' -Ok $scopeOk -Detail ("test_boot=18720B sha16={0} tail={1}B" -f $testBootSha, $tailLen)

# --- T17b: restore script shape + size guard (text only, not executed) ---
$restoreReadback = Join-Path $runDir 'planned-boot-restore-readback.bin'
$restoreLines = Get-P16BootRestoreLines -BackupBin $synthBackupPath -ReadbackPath $restoreReadback
$shapeOk = ($restoreLines.Count -eq 5) -and
    ($restoreLines[0] -eq 'h') -and ($restoreLines[4] -eq 'qc') -and
    ($restoreLines[1] -eq ('loadbin "{0}", 0x{1:X8}' -f $synthBackupPath, $script:P16BootRegionBase)) -and
    ($restoreLines[2] -eq ('verifybin "{0}", 0x{1:X8}' -f $synthBackupPath, $script:P16BootRegionBase)) -and
    ($restoreLines[3] -eq ('savebin "{0}", 0x{1:X8}, 0x{2:X}' -f $restoreReadback, $script:P16BootRegionBase, $script:P16BootAffectedLength))
Write-VerifyResult -Name 'T17b boot restore lines shape' -Ok $shapeOk -Detail ("lines={0}" -f $restoreLines.Count)

# Size guard: a restore input that is not exactly the affected region
# length must be rejected before any J-Link session starts.
$rejectedBadLen = $false
try { Invoke-P16BootRegionRestore -BackupBin $shortBackupPath -RunDirectory $runDir -Label 'guard-short' | Out-Null }
catch { $rejectedBadLen = $true }
Write-VerifyResult -Name 'T17c restore size guard fail-closed' -Ok $rejectedBadLen

# --- T18: both control-write entry points gate BEFORE writing ---
# Invoke-P16StartEncodedControl (the command-session entry used by
# S2/S3/S5) and Write-P16BlockInPlace must each run the invalidate gate
# before any body word is written. Static source assertion (offline):
# the first Invoke-P16ControlInvalidate occurrence inside each function
# body must precede its first Get-P16WordWriteLines occurrence.
$commonSrc = Join-Path $repoRoot 'Tools\jlink\p1-6-common.ps1'
$srcText = [System.IO.File]::ReadAllText($commonSrc)
$gateOk = $true
foreach ($fnName in @('Invoke-P16StartEncodedControl', 'Write-P16BlockInPlace')) {
    $m = [regex]::Match($srcText,
        ('(?s)function ' + $fnName + ' \{.*?\r?\n\}'))
    if (-not $m.Success) { $gateOk = $false; continue }
    $gateIdx = $m.Value.IndexOf('Invoke-P16ControlInvalidate')
    $writeIdx = $m.Value.IndexOf('Get-P16WordWriteLines')
    if ($gateIdx -lt 0 -or $writeIdx -lt 0 -or $gateIdx -gt $writeIdx) {
        $gateOk = $false
    }
}
Write-VerifyResult -Name 'T18 write entrypoints gated before body write' -Ok $gateOk

Write-Output ('verify_total passed={0} failed={1}' -f $script:Passed, $script:Failed)
if ($script:Failed -ne 0) {
    Write-Output 'VERIFY_RESULT=FAIL'
    exit 1
}
Write-Output 'VERIFY_RESULT=PASS'
exit 0
