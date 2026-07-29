[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$BuildDirectory,
    [Parameter(Mandatory = $true)][string]$AssetDirectory,
    [string]$RunDirectory = '',
    [string[]]$Rows = @(
        '01', '02', '04', '06', '08', '09', '10',
        '11', '12', '13', '14', '18', '19', '20'),
    [switch]$ExecuteBoard,
    [switch]$AssumeS0
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'p1-6-common.ps1')

$automaticRows = @(
    '01', '02', '04', '06', '08', '09', '10',
    '11', '12', '13', '14', '18', '19', '20')
$physicalRows = @('03', '05', '07', '15', '16', '17')
$build = (Resolve-Path $BuildDirectory).Path
$assets = (Resolve-Path $AssetDirectory).Path
if ([string]::IsNullOrWhiteSpace($RunDirectory)) {
    $RunDirectory = Join-Path $script:P1RepoRoot '.cache\p1-6-matrix-20260729'
}
[System.IO.Directory]::CreateDirectory($RunDirectory) | Out-Null
$RunDirectory = (Resolve-Path $RunDirectory).Path

foreach ($row in $Rows) {
    if ($row -notin $automaticRows) {
        throw "P1-6 row is not in the frozen AUTO set: $row"
    }
}

$bootBin = Join-Path $build 'boot\X-Track-Boot.bin'
$v0Bin = Join-Path $assets 'V0-final.bin'
$v1Bin = Join-Path $assets 'V1-final.bin'
$assetManifestPath = Join-Path $assets 'assets.json'
foreach ($path in @($bootBin, $v0Bin, $v1Bin, $assetManifestPath)) {
    Assert-P1File $path
}
$assetManifest = Get-Content -LiteralPath $assetManifestPath -Raw | ConvertFrom-Json
$v0 = $assetManifest.'V0-final.bin'
$v1 = $assetManifest.'V1-final.bin'
$appLength = [uint32]$v0.length
$blockSize = 4096
$blockCount = [uint32][Math]::Ceiling($appLength / [double]$blockSize)
if ($appLength -ne [uint32]$v1.length -or $blockCount -ne 138) {
    throw 'Frozen P1-6 asset lengths or block count drifted'
}

$manifestPath = Join-Path $RunDirectory 'matrix-manifest.json'
$manifest = [ordered]@{
    checkout = $script:P1RepoRoot
    build_directory = $build
    asset_directory = $assets
    control_address = ('0x{0:X8}' -f $script:P16ControlAddress)
    control_size = $script:P16ControlSize
    automatic = $automaticRows
    physical_pending = $physicalRows
    block_size = $blockSize
    block_count = $blockCount
    candidate = [ordered]@{
        version_code = [uint32]$v1.version_code
        length = [uint32]$v1.length
        raw_sha256 = [string]$v1.raw_sha256
        double_zero_sha256 = [string]$v1.double_zero_sha256
        header_crc32 = [string]$v1.header_crc32
    }
    backup = [ordered]@{
        version_code = [uint32]$v0.version_code
        length = [uint32]$v0.length
        raw_sha256 = [string]$v0.raw_sha256
        double_zero_sha256 = [string]$v0.double_zero_sha256
        header_crc32 = [string]$v0.header_crc32
    }
    recovery = [ordered]@{
        version_code = [uint32]$v0.version_code
        length = [uint32]$v0.length
        raw_sha256 = [string]$v0.raw_sha256
        double_zero_sha256 = [string]$v0.double_zero_sha256
        header_crc32 = [string]$v0.header_crc32
    }
    baseline_evidence = [ordered]@{
        candidate = 'baseline-candidate-app-bcb-snapshot.json'
        backup = 'baseline-backup-slot-snapshot.json'
        recovery = 'baseline-recovery-slot-snapshot.json'
        s0 = 's0-stage.json'
        internal_raw = 's0-internal-v0.json'
    }
}
if (-not (Test-Path -LiteralPath $manifestPath)) {
    Write-P16Json -Value $manifest -Path $manifestPath
}

if (-not $ExecuteBoard) {
    Write-Output "P1_6_MATRIX_RUNNER=READY automatic=14 physical_pending=6 control=0x$('{0:X8}' -f $script:P16ControlAddress)"
    Write-Output ('P1_6_ROWS=' + ($Rows -join ','))
    exit 0
}

Stop-P1RttLogger
Stop-Process -Name 'JLinkRTTViewer' -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 250
Assert-P1NoRttViewer
Assert-P16NoJLinkProcess

$boardStatePath = Join-Path $RunDirectory 'board-state.json'
if ($AssumeS0) {
    $script:BoardState = [ordered]@{
        semantic_state = 'S0'
        candidate_damaged = $false
        backup_damaged = $false
        recovery_damaged = $false
        last_row = $null
    }
    Write-P16Json -Value $script:BoardState -Path $boardStatePath
}
elseif (Test-Path -LiteralPath $boardStatePath) {
    $script:BoardState = Get-Content -LiteralPath $boardStatePath -Raw | ConvertFrom-Json
}
else {
    throw 'Board state is unknown. Use -AssumeS0 only after a fresh S0 snapshot.'
}

$script:RowDirectory = ''
$script:RowTrajectory = $null
$script:Terminal = $null
$script:FinalRecord = $null

function Assert-P16State {
    param(
        [Parameter(Mandatory = $true)]$Result,
        [Parameter(Mandatory = $true)][uint32]$State,
        [Parameter(Mandatory = $true)][uint32]$BootTry,
        [Parameter(Mandatory = $true)][uint32]$CopyPhase,
        [Parameter(Mandatory = $true)][uint32]$ResumeBlock,
        [Parameter(Mandatory = $true)][uint32]$CurVcode,
        [Parameter(Mandatory = $true)][uint32]$CandVcode,
        [Parameter(Mandatory = $true)][uint32]$BackupVcode,
        [int64]$AppVcode = -1,
        [string]$AppSha256 = ''
    )
    if ([uint32]$Result.active -notin @(1, 2) -or
        [uint32]$Result.state -ne $State -or
        [uint32]$Result.boot_try -ne $BootTry -or
        [uint32]$Result.copy_phase -ne $CopyPhase -or
        [uint32]$Result.resume_block -ne $ResumeBlock -or
        [uint32]$Result.cur_vcode -ne $CurVcode -or
        [uint32]$Result.cand_vcode -ne $CandVcode -or
        [uint32]$Result.backup_vcode -ne $BackupVcode) {
        throw ('Unexpected P1-6 BCB state: state={0} try={1} phase={2} resume={3} ' +
               'cur={4} cand={5} backup={6}') -f
            $Result.state, $Result.boot_try, $Result.copy_phase,
            $Result.resume_block, $Result.cur_vcode, $Result.cand_vcode,
            $Result.backup_vcode
    }
    if ($AppVcode -ge 0 -and
        ([uint32]$Result.app_result -ne 1 -or
         [uint32]$Result.app_vcode -ne [uint32]$AppVcode)) {
        throw "Unexpected P1-6 internal App version: $($Result.app_vcode)"
    }
    if (-not [string]::IsNullOrWhiteSpace($AppSha256) -and
        [string]$Result.app_sha256 -ne $AppSha256) {
        throw "Unexpected P1-6 internal App double-zero SHA: $($Result.app_sha256)"
    }
}

function Assert-P16S0 {
    param([Parameter(Mandatory = $true)]$Result)
    Assert-P16State -Result $Result -State 1 -BootTry 3 -CopyPhase 0 `
        -ResumeBlock 0 -CurVcode 20800 -CandVcode 20801 `
        -BackupVcode 20800 -AppVcode 20800 `
        -AppSha256 ([string]$v0.double_zero_sha256)
}

function Add-P16Trajectory {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)]$Result,
        [string]$Mechanism = ''
    )
    Write-P16Json -Value $Result -Path (Join-Path $script:RowDirectory ($Label + '.json'))
    $entry = [ordered]@{
        label = $Label
        mechanism = $Mechanism
        active = [uint32]$Result.active
        state = [uint32]$Result.state
        boot_try = [uint32]$Result.boot_try
        copy_phase = [uint32]$Result.copy_phase
        resume_block = [uint32]$Result.resume_block
        seq = [uint32]$Result.seq
        cur_vcode = [uint32]$Result.cur_vcode
        cand_vcode = [uint32]$Result.cand_vcode
        backup_vcode = [uint32]$Result.backup_vcode
        app_result = [uint32]$Result.app_result
        app_vcode = [uint32]$Result.app_vcode
        app_sha256 = [string]$Result.app_sha256
        checkpoint = [uint32]$Result.observed_checkpoint
        checkpoint_arg0 = [uint32]$Result.observed_arg0
        checkpoint_arg1 = [uint32]$Result.observed_arg1
        bcb_a_raw = [string]$Result.bcb_a_raw
        bcb_b_raw = [string]$Result.bcb_b_raw
    }
    $script:RowTrajectory.Add([pscustomobject]$entry)
}

function Assert-P16Checkpoint {
    param(
        [Parameter(Mandatory = $true)]$Run,
        [Parameter(Mandatory = $true)][uint32]$Checkpoint,
        [Parameter(Mandatory = $true)][uint32]$Arg0,
        [Parameter(Mandatory = $true)][uint32]$Arg1
    )
    $result = $Run.Result
    if ([uint32]$result.magic -ne $script:P16MagicArm -or
        -not [bool]$result.arm_valid -or
        [uint32]$result.status -ne $script:P16StatusCheckpoint -or
        [uint32]$result.observed_checkpoint -ne $Checkpoint -or
        [uint32]$result.observed_arg0 -ne $Arg0 -or
        [uint32]$result.observed_arg1 -ne $Arg1) {
        throw "Checkpoint evidence mismatch for CP$Checkpoint"
    }
}

function Start-P16RowCheckpoint {
    param(
        [Parameter(Mandatory = $true)][uint32]$Checkpoint,
        [Parameter(Mandatory = $true)][uint32]$Arg0,
        [Parameter(Mandatory = $true)][uint32]$Arg1,
        [Parameter(Mandatory = $true)][string]$Label,
        [int]$MaxWaitSeconds = 420
    )
    $run = Invoke-P16ArmCheckpoint -Checkpoint $Checkpoint -Arg0 $Arg0 `
        -Arg1 $Arg1 -RunDirectory $script:RowDirectory -Label $Label `
        -PollMilliseconds 30000 -MaxWaitSeconds $MaxWaitSeconds
    Assert-P16Checkpoint -Run $run -Checkpoint $Checkpoint -Arg0 $Arg0 -Arg1 $Arg1
    Add-P16Trajectory -Label $Label -Result $run.Result `
        -Mechanism 'ARM block written wordwise, magic last, then ordinary reset'
    return $run
}

function Move-P16RowCheckpoint {
    param(
        [Parameter(Mandatory = $true)][uint32]$Checkpoint,
        [Parameter(Mandatory = $true)][uint32]$Arg0,
        [Parameter(Mandatory = $true)][uint32]$Arg1,
        [Parameter(Mandatory = $true)][ValidateSet('Reset', 'Continue')][string]$StartMode,
        [Parameter(Mandatory = $true)][string]$Label,
        [int]$MaxWaitSeconds = 420
    )
    $run = Move-P16Checkpoint -Checkpoint $Checkpoint -Arg0 $Arg0 `
        -Arg1 $Arg1 -StartMode $StartMode `
        -RunDirectory $script:RowDirectory -Label $Label `
        -PollMilliseconds 30000 -MaxWaitSeconds $MaxWaitSeconds
    Assert-P16Checkpoint -Run $run -Checkpoint $Checkpoint -Arg0 $Arg0 -Arg1 $Arg1
    $mechanism = if ($StartMode -eq 'Reset') {
        'In-place ARM retarget, wordwise magic-last write, then ordinary reset'
    }
    else {
        'In-place ARM retarget, wordwise magic-last write, then continue current halt point'
    }
    Add-P16Trajectory -Label $Label -Result $run.Result -Mechanism $mechanism
    return $run
}

function Capture-P16BlockExpectation {
    param(
        [Parameter(Mandatory = $true)][uint32]$Block,
        [Parameter(Mandatory = $true)][ValidateSet('Erased', 'V0', 'V1')][string]$Expected,
        [Parameter(Mandatory = $true)][string]$Label
    )
    $address = [uint32]($script:P1AppAddress + ($Block * $blockSize))
    $captured = Save-P16MemoryRange -Address $address -Length $blockSize `
        -RunDirectory $script:RowDirectory -Label $Label
    $expectedPath = Join-Path $script:RowDirectory ($Label + '.expected.bin')
    if ($Expected -eq 'Erased') {
        $expectedBytes = New-Object byte[] $blockSize
        for ($index = 0; $index -lt $expectedBytes.Length; $index++) {
            $expectedBytes[$index] = 0xFF
        }
    }
    else {
        $assetPath = if ($Expected -eq 'V0') { $v0Bin } else { $v1Bin }
        $assetBytes = [System.IO.File]::ReadAllBytes($assetPath)
        $offset = [int]($Block * $blockSize)
        $expectedBytes = New-Object byte[] $blockSize
        [Array]::Copy($assetBytes, $offset, $expectedBytes, 0, $blockSize)
    }
    [System.IO.File]::WriteAllBytes($expectedPath, $expectedBytes)
    $actualHash = (Get-FileHash -LiteralPath $captured -Algorithm SHA256).Hash.ToLowerInvariant()
    $expectedHash = (Get-FileHash -LiteralPath $expectedPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualHash -ne $expectedHash) {
        throw "Internal block $Block did not match $Expected at $Label"
    }
    $record = [ordered]@{
        block = $Block
        address = ('0x{0:X8}' -f $address)
        expected = $Expected
        captured_sha256 = $actualHash
        expected_sha256 = $expectedHash
    }
    Write-P16Json -Value $record -Path (Join-Path $script:RowDirectory ($Label + '.comparison.json'))
}

function Set-P16BoardState {
    param(
        [Parameter(Mandatory = $true)][string]$SemanticState,
        [bool]$CandidateDamaged = $false,
        [bool]$BackupDamaged = $false,
        [bool]$RecoveryDamaged = $false,
        [string]$LastRow = ''
    )
    $script:BoardState = [ordered]@{
        semantic_state = $SemanticState
        candidate_damaged = $CandidateDamaged
        backup_damaged = $BackupDamaged
        recovery_damaged = $RecoveryDamaged
        last_row = $LastRow
    }
    Write-P16Json -Value $script:BoardState -Path $boardStatePath
}

function Restore-P16S0 {
    param([Parameter(Mandatory = $true)][string]$PreparationDirectory)
    [System.IO.Directory]::CreateDirectory($PreparationDirectory) | Out-Null
    Write-Output 'P1_6_PREP=FLASH_V0'
    Invoke-P16FlashApp -AppBin $v0Bin -RunDirectory $PreparationDirectory `
        -Label 'restore-internal-v0' | Out-Null
    Write-Output 'P1_6_PREP=CLEAR_BCB'
    Invoke-P16Command -Opcode $script:P16OpcodeClearBcb `
        -RunDirectory $PreparationDirectory -Label 'clear-bcb' `
        -PollMilliseconds 10000 -MaxWaitSeconds 120 | Out-Null
    Invoke-P16OrdinaryResetEvidence -RunDirectory $PreparationDirectory `
        -Label 'establish-confirmed-v0' -WaitMilliseconds 45000 | Out-Null

    if ([bool]$script:BoardState.candidate_damaged) {
        Write-Output 'P1_6_PREP=REPAIR_CANDIDATE_V1'
        Invoke-P16FlashApp -AppBin $v1Bin -RunDirectory $PreparationDirectory `
            -Label 'flash-v1-for-candidate' | Out-Null
        Invoke-P16Command -Opcode $script:P16OpcodeInstallSlot `
            -Arg0 $script:P16SlotCandidate -RunDirectory $PreparationDirectory `
            -Label 'install-candidate-v1' -PollMilliseconds 30000 `
            -MaxWaitSeconds 300 | Out-Null
        Invoke-P16FlashApp -AppBin $v0Bin -RunDirectory $PreparationDirectory `
            -Label 'restore-v0-after-candidate' | Out-Null
    }
    if ([bool]$script:BoardState.backup_damaged) {
        Write-Output 'P1_6_PREP=REPAIR_BACKUP_V0'
        Invoke-P16Command -Opcode $script:P16OpcodeInstallSlot `
            -Arg0 $script:P16SlotBackup -RunDirectory $PreparationDirectory `
            -Label 'install-backup-v0' -PollMilliseconds 30000 `
            -MaxWaitSeconds 300 | Out-Null
    }
    if ([bool]$script:BoardState.recovery_damaged) {
        Write-Output 'P1_6_PREP=REPAIR_RECOVERY_V0'
        Invoke-P16Command -Opcode $script:P16OpcodeInstallSlot `
            -Arg0 $script:P16SlotRecovery -RunDirectory $PreparationDirectory `
            -Label 'install-recovery-v0' -PollMilliseconds 30000 `
            -MaxWaitSeconds 300 | Out-Null
    }

    Write-Output 'P1_6_PREP=STAGE_S0'
    $stage = Invoke-P16Command -Opcode $script:P16OpcodeStageSlots `
        -RunDirectory $PreparationDirectory -Label 'stage-s0' `
        -PollMilliseconds 30000 -MaxWaitSeconds 300
    Assert-P16S0 -Result $stage.Result
    Write-P16Json -Value $stage.Result `
        -Path (Join-Path $PreparationDirectory 'stage-s0-result.json')
    Set-P16BoardState -SemanticState 'S0'
}

function Snapshot-P16RowPrecondition {
    $snapshot = Invoke-P16Command -Opcode $script:P16OpcodeSnapshot `
        -Arg0 0 -Arg1 0 -RunDirectory $script:RowDirectory `
        -Label 'pre-s0-snapshot' -PollMilliseconds 15000 `
        -MaxWaitSeconds 120
    Assert-P16S0 -Result $snapshot.Result
    Add-P16Trajectory -Label 'pre-s0-snapshot' -Result $snapshot.Result `
        -Mechanism 'Boot command snapshot before injection; no state-machine execution'
}

function Move-P16ToV1Confirmed {
    $confirmed = Move-P16RowCheckpoint -Checkpoint 12 -Arg0 20801 -Arg1 4 `
        -StartMode Continue -Label 'final-app-confirmed-v1' -MaxWaitSeconds 480
    Assert-P16State -Result $confirmed.Result -State 4 -BootTry 0 `
        -CopyPhase 0 -ResumeBlock 0 -CurVcode 20801 -CandVcode 20801 `
        -BackupVcode 20800 -AppVcode 20801
    return $confirmed
}

function Move-P16ToV0RollbackConfirmed {
    $confirmed = Move-P16RowCheckpoint -Checkpoint 11 -Arg0 0 -Arg1 0 `
        -StartMode Continue -Label 'final-rollback-confirmed-v0' `
        -MaxWaitSeconds 420
    Assert-P16State -Result $confirmed.Result -State 4 -BootTry 0 `
        -CopyPhase 0 -ResumeBlock 0 -CurVcode 20800 -CandVcode 20801 `
        -BackupVcode 20800 -AppVcode 20800 `
        -AppSha256 ([string]$v0.double_zero_sha256)
    return $confirmed
}

function Move-P16S0ToT0 {
    $t3 = Start-P16RowCheckpoint -Checkpoint 8 -Arg0 0 -Arg1 3 `
        -Label 'setup-test-boot-t3' -MaxWaitSeconds 420
    Assert-P16State -Result $t3.Result -State 3 -BootTry 3 `
        -CopyPhase 0 -ResumeBlock 0 -CurVcode 20800 -CandVcode 20801 `
        -BackupVcode 20800 -AppVcode 20801 `
        -AppSha256 ([string]$v1.double_zero_sha256)
    $t2 = Move-P16RowCheckpoint -Checkpoint 9 -Arg0 2 -Arg1 0 `
        -StartMode Reset -Label 'setup-reset-1-t2'
    Assert-P16State -Result $t2.Result -State 3 -BootTry 2 `
        -CopyPhase 0 -ResumeBlock 0 -CurVcode 20800 -CandVcode 20801 `
        -BackupVcode 20800 -AppVcode 20801 `
        -AppSha256 ([string]$v1.double_zero_sha256)
    $t1 = Move-P16RowCheckpoint -Checkpoint 9 -Arg0 1 -Arg1 0 `
        -StartMode Reset -Label 'setup-reset-2-t1'
    Assert-P16State -Result $t1.Result -State 3 -BootTry 1 `
        -CopyPhase 0 -ResumeBlock 0 -CurVcode 20800 -CandVcode 20801 `
        -BackupVcode 20800 -AppVcode 20801 `
        -AppSha256 ([string]$v1.double_zero_sha256)
    $t0 = Move-P16RowCheckpoint -Checkpoint 9 -Arg0 0 -Arg1 0 `
        -StartMode Reset -Label 'setup-reset-3-t0'
    Assert-P16State -Result $t0.Result -State 3 -BootTry 0 `
        -CopyPhase 0 -ResumeBlock 0 -CurVcode 20800 -CandVcode 20801 `
        -BackupVcode 20800 -AppVcode 20801 `
        -AppSha256 ([string]$v1.double_zero_sha256)
    return $t0
}

function Complete-P16Bootable {
    param(
        [Parameter(Mandatory = $true)][ValidateSet('V0', 'V1')][string]$Expected,
        [Parameter(Mandatory = $true)][string]$ResetLabel
    )
    Invoke-P16OrdinaryResetEvidence -RunDirectory $script:RowDirectory `
        -Label $ResetLabel -WaitMilliseconds 45000 | Out-Null
    $snapshot = Invoke-P16Command -Opcode $script:P16OpcodeSnapshot `
        -Arg0 0 -Arg1 0 -RunDirectory $script:RowDirectory `
        -Label 'final-app-bcb-snapshot' -PollMilliseconds 15000 `
        -MaxWaitSeconds 120
    $asset = if ($Expected -eq 'V0') { $v0 } else { $v1 }
    Assert-P16State -Result $snapshot.Result -State 4 -BootTry 0 `
        -CopyPhase 0 -ResumeBlock 0 `
        -CurVcode ([uint32]$asset.version_code) -CandVcode 20801 `
        -BackupVcode 20800 -AppVcode ([uint32]$asset.version_code) `
        -AppSha256 ([string]$asset.double_zero_sha256)
    Add-P16Trajectory -Label 'final-app-bcb-snapshot' `
        -Result $snapshot.Result -Mechanism 'Final validated Boot command snapshot'
    $raw = Save-P16InternalImage -Length $appLength `
        -RunDirectory $script:RowDirectory -Label 'final-internal-app'
    if ($raw.raw_sha256 -ne [string]$asset.raw_sha256) {
        throw "Final internal raw SHA mismatch for $Expected"
    }
    $script:Terminal = 'BOOTABLE'
    $script:FinalRecord = [ordered]@{
        expected = $Expected
        version_code = [uint32]$asset.version_code
        raw_sha256 = [string]$raw.raw_sha256
        double_zero_sha256 = [string]$snapshot.Result.app_sha256
        header_crc32 = ('{0:x8}' -f [uint32]$snapshot.Result.app_header_crc32)
        terminal = $script:Terminal
    }
}

function Complete-P16PhysicalRecovery {
    param([Parameter(Mandatory = $true)]$CheckpointResult)
    Assert-P16State -Result $CheckpointResult -State 5 -BootTry 0 `
        -CopyPhase 2 -ResumeBlock 0 -CurVcode 20800 -CandVcode 20801 `
        -BackupVcode 20800 -AppVcode 20801 `
        -AppSha256 ([string]$v1.double_zero_sha256)
    $raw = Save-P16InternalImage -Length $appLength `
        -RunDirectory $script:RowDirectory -Label 'final-internal-app'
    if ($raw.raw_sha256 -ne [string]$v1.raw_sha256) {
        throw 'PHYSICAL_RECOVERY path erased or changed the internal V1 image'
    }
    $script:Terminal = 'PHYSICAL_RECOVERY'
    $script:FinalRecord = [ordered]@{
        expected = 'V1 retained'
        version_code = 20801
        raw_sha256 = [string]$raw.raw_sha256
        double_zero_sha256 = [string]$CheckpointResult.app_sha256
        header_crc32 = ('{0:x8}' -f [uint32]$CheckpointResult.app_header_crc32)
        terminal = $script:Terminal
    }
}

function Invoke-P16Row01 {
    $corrupt = Invoke-P16Command -Opcode $script:P16OpcodeCorruptSlot `
        -Arg0 $script:P16SlotCandidate -Arg1 0 `
        -RunDirectory $script:RowDirectory -Label 'inject-corrupt-candidate' `
        -PollMilliseconds 15000 -MaxWaitSeconds 120
    Assert-P16S0 -Result $corrupt.Result
    Add-P16Trajectory -Label 'inject-corrupt-candidate' -Result $corrupt.Result `
        -Mechanism 'Candidate payload bit cleared after marker-valid installation'
    $rollback = Move-P16RowCheckpoint -Checkpoint 10 -Arg0 2 -Arg1 0 `
        -StartMode Reset -Label 'post-reset-rollback-r0'
    Assert-P16State -Result $rollback.Result -State 5 -BootTry 0 `
        -CopyPhase 2 -ResumeBlock 0 -CurVcode 20800 -CandVcode 20801 `
        -BackupVcode 20800 -AppVcode 20800 `
        -AppSha256 ([string]$v0.double_zero_sha256)
    Move-P16ToV0RollbackConfirmed | Out-Null
    Complete-P16Bootable -Expected V0 -ResetLabel 'terminal-bootable-reset'
    Set-P16BoardState -SemanticState 'CONFIRMED_V0' `
        -CandidateDamaged $true -LastRow '01'
}

function Invoke-P16Row02 {
    $first = Start-P16RowCheckpoint -Checkpoint 1 -Arg0 0 -Arg1 0 `
        -Label 'candidate-validated-before-injection'
    Assert-P16S0 -Result $first.Result
    $second = Move-P16RowCheckpoint -Checkpoint 1 -Arg0 0 -Arg1 0 `
        -StartMode Reset -Label 'post-reset-candidate-revalidated'
    Assert-P16S0 -Result $second.Result
    if ([string]$first.Result.bcb_a_raw -ne [string]$second.Result.bcb_a_raw -or
        [string]$first.Result.bcb_b_raw -ne [string]$second.Result.bcb_b_raw) {
        throw 'Row 02 reset changed the authoritative STAGED BCB before APPLYING commit'
    }
    $applying = Move-P16RowCheckpoint -Checkpoint 2 -Arg0 1 -Arg1 0 `
        -StartMode Continue -Label 'restart-applying-a0'
    Assert-P16State -Result $applying.Result -State 2 -BootTry 0 `
        -CopyPhase 1 -ResumeBlock 0 -CurVcode 20800 -CandVcode 20801 `
        -BackupVcode 20800 -AppVcode 20800 `
        -AppSha256 ([string]$v0.double_zero_sha256)
    Move-P16ToV1Confirmed | Out-Null
    Complete-P16Bootable -Expected V1 -ResetLabel 'terminal-bootable-reset'
    Set-P16BoardState -SemanticState 'CONFIRMED_V1' -LastRow '02'
}

function Invoke-P16Row04 {
    $pre = Start-P16RowCheckpoint -Checkpoint 2 -Arg0 1 -Arg1 0 `
        -Label 'pre-injection-applying-a0'
    Assert-P16State -Result $pre.Result -State 2 -BootTry 0 `
        -CopyPhase 1 -ResumeBlock 0 -CurVcode 20800 -CandVcode 20801 `
        -BackupVcode 20800 -AppVcode 20800 `
        -AppSha256 ([string]$v0.double_zero_sha256)
    $post = Move-P16RowCheckpoint -Checkpoint 3 -Arg0 1 -Arg1 0 `
        -StartMode Reset -Label 'post-reset-before-erase-block0'
    Assert-P16State -Result $post.Result -State 2 -BootTry 0 `
        -CopyPhase 1 -ResumeBlock 0 -CurVcode 20800 -CandVcode 20801 `
        -BackupVcode 20800
    Move-P16ToV1Confirmed | Out-Null
    Complete-P16Bootable -Expected V1 -ResetLabel 'terminal-bootable-reset'
    Set-P16BoardState -SemanticState 'CONFIRMED_V1' -LastRow '04'
}

function Invoke-P16Row06 {
    $pre = Start-P16RowCheckpoint -Checkpoint 4 -Arg0 1 -Arg1 64 `
        -Label 'pre-injection-after-erase-block64'
    Assert-P16State -Result $pre.Result -State 2 -BootTry 0 `
        -CopyPhase 1 -ResumeBlock 64 -CurVcode 20800 -CandVcode 20801 `
        -BackupVcode 20800
    Capture-P16BlockExpectation -Block 64 -Expected Erased `
        -Label 'pre-injection-block64-erased'
    $post = Move-P16RowCheckpoint -Checkpoint 3 -Arg0 1 -Arg1 64 `
        -StartMode Reset -Label 'post-reset-before-reerase-block64'
    Assert-P16State -Result $post.Result -State 2 -BootTry 0 `
        -CopyPhase 1 -ResumeBlock 64 -CurVcode 20800 -CandVcode 20801 `
        -BackupVcode 20800
    Capture-P16BlockExpectation -Block 64 -Expected Erased `
        -Label 'post-reset-block64-still-erased'
    Move-P16ToV1Confirmed | Out-Null
    Complete-P16Bootable -Expected V1 -ResetLabel 'terminal-bootable-reset'
    Set-P16BoardState -SemanticState 'CONFIRMED_V1' -LastRow '06'
}

function Invoke-P16Row08 {
    $pre = Start-P16RowCheckpoint -Checkpoint 5 -Arg0 1 -Arg1 64 `
        -Label 'pre-injection-after-readback-block64'
    Assert-P16State -Result $pre.Result -State 2 -BootTry 0 `
        -CopyPhase 1 -ResumeBlock 64 -CurVcode 20800 -CandVcode 20801 `
        -BackupVcode 20800
    Capture-P16BlockExpectation -Block 64 -Expected V1 `
        -Label 'pre-injection-block64-programmed'
    $post = Move-P16RowCheckpoint -Checkpoint 3 -Arg0 1 -Arg1 64 `
        -StartMode Reset -Label 'post-reset-repeat-block64'
    Assert-P16State -Result $post.Result -State 2 -BootTry 0 `
        -CopyPhase 1 -ResumeBlock 64 -CurVcode 20800 -CandVcode 20801 `
        -BackupVcode 20800
    Capture-P16BlockExpectation -Block 64 -Expected V1 `
        -Label 'post-reset-block64-before-repeat-erase'
    Move-P16ToV1Confirmed | Out-Null
    Complete-P16Bootable -Expected V1 -ResetLabel 'terminal-bootable-reset'
    Set-P16BoardState -SemanticState 'CONFIRMED_V1' -LastRow '08'
}

function Invoke-P16Row09 {
    $pre = Start-P16RowCheckpoint -Checkpoint 6 -Arg0 1 -Arg1 65 `
        -Label 'pre-injection-resume65-committed'
    Assert-P16State -Result $pre.Result -State 2 -BootTry 0 `
        -CopyPhase 1 -ResumeBlock 65 -CurVcode 20800 -CandVcode 20801 `
        -BackupVcode 20800
    Capture-P16BlockExpectation -Block 64 -Expected V1 `
        -Label 'pre-injection-committed-prefix-block64'
    $post = Move-P16RowCheckpoint -Checkpoint 3 -Arg0 1 -Arg1 65 `
        -StartMode Reset -Label 'post-reset-next-block65'
    Assert-P16State -Result $post.Result -State 2 -BootTry 0 `
        -CopyPhase 1 -ResumeBlock 65 -CurVcode 20800 -CandVcode 20801 `
        -BackupVcode 20800
    Capture-P16BlockExpectation -Block 64 -Expected V1 `
        -Label 'post-reset-prefix-block64-preserved'
    Move-P16ToV1Confirmed | Out-Null
    Complete-P16Bootable -Expected V1 -ResetLabel 'terminal-bootable-reset'
    Set-P16BoardState -SemanticState 'CONFIRMED_V1' -LastRow '09'
}

function Invoke-P16Row10 {
    $pre = Start-P16RowCheckpoint -Checkpoint 7 -Arg0 1 -Arg1 $blockCount `
        -Label 'pre-injection-apply-copy-complete'
    Assert-P16State -Result $pre.Result -State 2 -BootTry 0 `
        -CopyPhase 1 -ResumeBlock $blockCount -CurVcode 20800 `
        -CandVcode 20801 -BackupVcode 20800 -AppVcode 20801 `
        -AppSha256 ([string]$v1.double_zero_sha256)
    $post = Move-P16RowCheckpoint -Checkpoint 8 -Arg0 0 -Arg1 3 `
        -StartMode Reset -Label 'post-reset-test-boot-t3'
    Assert-P16State -Result $post.Result -State 3 -BootTry 3 `
        -CopyPhase 0 -ResumeBlock 0 -CurVcode 20800 -CandVcode 20801 `
        -BackupVcode 20800 -AppVcode 20801 `
        -AppSha256 ([string]$v1.double_zero_sha256)
    Move-P16ToV1Confirmed | Out-Null
    Complete-P16Bootable -Expected V1 -ResetLabel 'terminal-bootable-reset'
    Set-P16BoardState -SemanticState 'CONFIRMED_V1' -LastRow '10'
}

function Invoke-P16Row11 {
    $pre = Start-P16RowCheckpoint -Checkpoint 8 -Arg0 0 -Arg1 3 `
        -Label 'pre-injection-test-boot-t3'
    Assert-P16State -Result $pre.Result -State 3 -BootTry 3 `
        -CopyPhase 0 -ResumeBlock 0 -CurVcode 20800 -CandVcode 20801 `
        -BackupVcode 20800 -AppVcode 20801 `
        -AppSha256 ([string]$v1.double_zero_sha256)
    $post = Move-P16RowCheckpoint -Checkpoint 9 -Arg0 2 -Arg1 0 `
        -StartMode Reset -Label 'post-reset-test-boot-t2'
    Assert-P16State -Result $post.Result -State 3 -BootTry 2 `
        -CopyPhase 0 -ResumeBlock 0 -CurVcode 20800 -CandVcode 20801 `
        -BackupVcode 20800 -AppVcode 20801 `
        -AppSha256 ([string]$v1.double_zero_sha256)
    Move-P16ToV1Confirmed | Out-Null
    Complete-P16Bootable -Expected V1 -ResetLabel 'terminal-bootable-reset'
    Set-P16BoardState -SemanticState 'CONFIRMED_V1' -LastRow '11'
}

function Invoke-P16Row12 {
    $pre = Start-P16RowCheckpoint -Checkpoint 9 -Arg0 2 -Arg1 0 `
        -Label 'pre-injection-test-boot-t2'
    Assert-P16State -Result $pre.Result -State 3 -BootTry 2 `
        -CopyPhase 0 -ResumeBlock 0 -CurVcode 20800 -CandVcode 20801 `
        -BackupVcode 20800 -AppVcode 20801 `
        -AppSha256 ([string]$v1.double_zero_sha256)
    $post = Move-P16RowCheckpoint -Checkpoint 9 -Arg0 1 -Arg1 0 `
        -StartMode Reset -Label 'post-reset-test-boot-t1'
    Assert-P16State -Result $post.Result -State 3 -BootTry 1 `
        -CopyPhase 0 -ResumeBlock 0 -CurVcode 20800 -CandVcode 20801 `
        -BackupVcode 20800 -AppVcode 20801 `
        -AppSha256 ([string]$v1.double_zero_sha256)
    Move-P16ToV1Confirmed | Out-Null
    Complete-P16Bootable -Expected V1 -ResetLabel 'terminal-bootable-reset'
    Set-P16BoardState -SemanticState 'CONFIRMED_V1' -LastRow '12'
}

function Invoke-P16Row13 {
    $pre = Start-P16RowCheckpoint -Checkpoint 12 -Arg0 20801 -Arg1 4 `
        -Label 'pre-injection-app-confirmed-v1' -MaxWaitSeconds 480
    Assert-P16State -Result $pre.Result -State 4 -BootTry 0 `
        -CopyPhase 0 -ResumeBlock 0 -CurVcode 20801 -CandVcode 20801 `
        -BackupVcode 20800 -AppVcode 20801
    Complete-P16Bootable -Expected V1 -ResetLabel 'injection-ordinary-reset'
    Set-P16BoardState -SemanticState 'CONFIRMED_V1' -LastRow '13'
}

function Invoke-P16Row14 {
    Move-P16S0ToT0 | Out-Null
    $rollback = Move-P16RowCheckpoint -Checkpoint 10 -Arg0 2 -Arg1 0 `
        -StartMode Reset -Label 'fourth-boot-rollback-r0'
    Assert-P16State -Result $rollback.Result -State 5 -BootTry 0 `
        -CopyPhase 2 -ResumeBlock 0 -CurVcode 20800 -CandVcode 20801 `
        -BackupVcode 20800 -AppVcode 20801 `
        -AppSha256 ([string]$v1.double_zero_sha256)
    Move-P16ToV0RollbackConfirmed | Out-Null
    Complete-P16Bootable -Expected V0 -ResetLabel 'terminal-bootable-reset'
    Set-P16BoardState -SemanticState 'CONFIRMED_V0' -LastRow '14'
}

function Invoke-P16Row18 {
    Move-P16S0ToT0 | Out-Null
    $pre = Move-P16RowCheckpoint -Checkpoint 6 -Arg0 2 -Arg1 65 `
        -StartMode Reset -Label 'pre-injection-rollback-resume65'
    Assert-P16State -Result $pre.Result -State 5 -BootTry 0 `
        -CopyPhase 2 -ResumeBlock 65 -CurVcode 20800 -CandVcode 20801 `
        -BackupVcode 20800
    Capture-P16BlockExpectation -Block 64 -Expected V0 `
        -Label 'pre-injection-rollback-prefix-block64-v0'
    $post = Move-P16RowCheckpoint -Checkpoint 3 -Arg0 2 -Arg1 65 `
        -StartMode Reset -Label 'post-reset-rollback-next-block65'
    Assert-P16State -Result $post.Result -State 5 -BootTry 0 `
        -CopyPhase 2 -ResumeBlock 65 -CurVcode 20800 -CandVcode 20801 `
        -BackupVcode 20800
    Capture-P16BlockExpectation -Block 64 -Expected V0 `
        -Label 'post-reset-rollback-prefix-block64-preserved'
    Move-P16ToV0RollbackConfirmed | Out-Null
    Complete-P16Bootable -Expected V0 -ResetLabel 'terminal-bootable-reset'
    Set-P16BoardState -SemanticState 'CONFIRMED_V0' -LastRow '18'
}

function Invoke-P16Row19 {
    Move-P16S0ToT0 | Out-Null
    $pre = Move-P16RowCheckpoint -Checkpoint 11 -Arg0 0 -Arg1 0 `
        -StartMode Reset -Label 'pre-injection-rollback-confirmed-v0' `
        -MaxWaitSeconds 420
    Assert-P16State -Result $pre.Result -State 4 -BootTry 0 `
        -CopyPhase 0 -ResumeBlock 0 -CurVcode 20800 -CandVcode 20801 `
        -BackupVcode 20800 -AppVcode 20800 `
        -AppSha256 ([string]$v0.double_zero_sha256)
    Complete-P16Bootable -Expected V0 -ResetLabel 'injection-ordinary-reset'
    Set-P16BoardState -SemanticState 'CONFIRMED_V0' -LastRow '19'
}

function Invoke-P16Row20 {
    Move-P16S0ToT0 | Out-Null
    $backup = Invoke-P16Command -Opcode $script:P16OpcodeCorruptSlot `
        -Arg0 $script:P16SlotBackup -Arg1 0 `
        -RunDirectory $script:RowDirectory -Label 'inject-corrupt-backup' `
        -PollMilliseconds 15000 -MaxWaitSeconds 120
    Assert-P16State -Result $backup.Result -State 3 -BootTry 0 `
        -CopyPhase 0 -ResumeBlock 0 -CurVcode 20800 -CandVcode 20801 `
        -BackupVcode 20800 -AppVcode 20801 `
        -AppSha256 ([string]$v1.double_zero_sha256)
    Add-P16Trajectory -Label 'inject-corrupt-backup' -Result $backup.Result `
        -Mechanism 'Backup payload bit cleared while command intercept holds T0'
    $recovery = Invoke-P16Command -Opcode $script:P16OpcodeCorruptSlot `
        -Arg0 $script:P16SlotRecovery -Arg1 0 `
        -RunDirectory $script:RowDirectory -Label 'inject-corrupt-recovery' `
        -PollMilliseconds 15000 -MaxWaitSeconds 120
    Assert-P16State -Result $recovery.Result -State 3 -BootTry 0 `
        -CopyPhase 0 -ResumeBlock 0 -CurVcode 20800 -CandVcode 20801 `
        -BackupVcode 20800 -AppVcode 20801 `
        -AppSha256 ([string]$v1.double_zero_sha256)
    Add-P16Trajectory -Label 'inject-corrupt-recovery' -Result $recovery.Result `
        -Mechanism 'Recovery payload bit cleared while command intercept holds T0'
    $physical = Move-P16RowCheckpoint -Checkpoint 13 `
        -Arg0 ([uint32]4294967293) -Arg1 5 -StartMode Reset `
        -Label 'terminal-physical-recovery' -MaxWaitSeconds 240
    Complete-P16PhysicalRecovery -CheckpointResult $physical.Result
    Set-P16BoardState -SemanticState 'PHYSICAL_RECOVERY' `
        -BackupDamaged $true -RecoveryDamaged $true -LastRow '20'
}

$assumeCurrentS0 = [bool]$AssumeS0
foreach ($row in $Rows) {
    $script:RowDirectory = Join-Path $RunDirectory ('row-' + $row)
    if (Test-Path -LiteralPath $script:RowDirectory) {
        throw "P1-6 row evidence directory already exists: $script:RowDirectory"
    }
    [System.IO.Directory]::CreateDirectory($script:RowDirectory) | Out-Null
    $script:RowTrajectory = New-Object System.Collections.Generic.List[object]
    $script:Terminal = $null
    $script:FinalRecord = $null

    $rowManifest = [ordered]@{
        row = $row
        execution = 'AUTO'
        candidate = $manifest.candidate
        backup = $manifest.backup
        recovery = $manifest.recovery
        control_address = $manifest.control_address
        checkpoint_source = [ordered]@{
            cp1 = 'boot/src/boot_state_machine.c:610 args=(copy_phase,resume_block)'
            cp2 = 'boot/src/boot_state_machine.c:622 args=(copy_phase,resume_block)'
            cp3_to_cp6 = 'boot/src/boot_state_machine.c:395-419 args=(copy_phase,block-or-resume)'
            cp7_to_cp11 = 'boot/src/boot_state_machine.c:655-801'
            cp12 = 'USER/HAL/HAL_EEPROM.cpp:125-133 args=(vcode,state)'
            cp13 = 'boot/src/boot_main.c:187-189 args=(status,state)'
        }
    }
    Write-P16Json -Value $rowManifest `
        -Path (Join-Path $script:RowDirectory 'row-manifest.json')

    if (-not $assumeCurrentS0) {
        Restore-P16S0 -PreparationDirectory `
            (Join-Path $script:RowDirectory '00-prepare-s0')
    }
    else {
        $assumeCurrentS0 = $false
    }
    Snapshot-P16RowPrecondition
    Write-Output "P1_6_ROW_START=$row"

    & (Get-Command ('Invoke-P16Row' + $row) -CommandType Function)
    if ($null -eq $script:Terminal -or $null -eq $script:FinalRecord) {
        throw "P1-6 row $row did not produce a terminal result"
    }
    $summary = [ordered]@{
        row = $row
        execution = 'AUTO'
        terminal = $script:Terminal
        trajectory = $script:RowTrajectory.ToArray()
        final = $script:FinalRecord
    }
    Write-P16Json -Value $summary `
        -Path (Join-Path $script:RowDirectory 'row-summary.json')
    Write-Output "P1_6_ROW_PASS=$row terminal=$script:Terminal"
}

Write-Output ('P1_6_MATRIX_ROWS_PASS=' + ($Rows -join ','))
