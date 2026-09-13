# P3-3 recovery command offline verification (2026-09-13).
# Scope: reuse the pure functions in Tools/jlink/p1-6-common.ps1 to verify,
# with no device access and no J-Link process:
#   1. CLEAR_BCB / SNAPSHOT command block generation + decode round trip
#   2. ARM checkpoint block generation + decode round trip
#   3. staged/committed commit ordering semantics (magic-zero staging)
#   4. Get-P16WordWriteLines generated J-Link script shape (text only,
#      never executed here)
#   5. fail-closed tamper rejection (CRC, inverse fields, magic, size)
# All outputs stay inside <repo>/.cache/p3-3-recovery-boot/cmd-verify/.

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
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

Write-Output ('verify_total passed={0} failed={1}' -f $script:Passed, $script:Failed)
if ($script:Failed -ne 0) {
    Write-Output 'VERIFY_RESULT=FAIL'
    exit 1
}
Write-Output 'VERIFY_RESULT=PASS'
exit 0
