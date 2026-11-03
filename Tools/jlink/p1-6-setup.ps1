[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidateSet('Seed', 'Restore')][string]$Action,
    [Parameter(Mandatory = $true)][string]$Plan,
    [Parameter(Mandatory = $true)][string]$RunDirectory
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'p1-6-common.ps1')
$p = Get-Content -LiteralPath $Plan -Raw | ConvertFrom-Json
$script:P16ProbeSerial = [int]$p.probeSerial
$script:P16ExpectedVtor = [uint32]$p.vtor
$script:P16SafeHalt = [uint32]$p.testSafeHalt
$RunDirectory = New-WorktreeDirectory -RepoRoot $script:P1RepoRoot -DirectoryPath $RunDirectory

function Get-PinnedFile($item) {
    $path = Join-Path $script:P1RepoRoot $item.path
    Assert-P1File $path
    if ((Get-Item -LiteralPath $path).Length -ne $item.bytes -or
        (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $item.sha256) {
        throw "Input mismatch: $path"
    }
    return $path
}

$originalBoot = Get-PinnedFile $p.originalBoot
$originalApp = Get-PinnedFile $p.originalApp
$testBoot = Get-PinnedFile $p.testBoot
$v0 = Get-PinnedFile $p.v0
$v1 = Get-PinnedFile $p.v1
foreach ($item in @($p.slots.candidate, $p.slots.backup, $p.slots.recovery)) { Get-PinnedFile $item | Out-Null }
Assert-P1NoRttViewer
Assert-P16NoJLinkProcess

function Run-Control([uint32]$Opcode, [uint32]$Arg0, [string]$Label) {
    return Invoke-P16Command -Opcode $Opcode -Arg0 $Arg0 -RunDirectory $RunDirectory `
        -Label $Label -PollMilliseconds 1000 -MaxWaitSeconds 300
}

if ($Action -eq 'Seed') {
    Invoke-P16IdleHalt -Address ([uint32]$p.safeHalt) -RunDirectory $RunDirectory -Label 'safe-halt' | Out-Null
    $log = Invoke-P16JLink -RunDirectory $RunDirectory -Label 'install-test-fixture' -TimeoutSeconds 300 -Lines @(
        'h', ('loadbin "{0}", 0x08000000' -f $testBoot),
        ('verifybin "{0}", 0x08000000' -f $testBoot),
        ('loadbin "{0}", 0x08010000' -f $v0), ('verifybin "{0}", 0x08010000' -f $v0),
        ('w4 0x{0:X8}, 0' -f $script:P16ControlAddress), 'qc'
    )
    if ([regex]::Matches((Get-Content -LiteralPath $log -Raw), 'Verify successful\.').Count -ne 2) {
        throw 'Test fixture verification missing'
    }
    $before = Run-Control $script:P16OpcodeSnapshot 0 'original-bcb-before-clear'
    if ([uint32]$before.Result.state -ne 4 -or [uint32]$before.Result.cur_vcode -ne 30313) {
        throw 'Original BCB is not confirmed 30313; retain snapshot and stop'
    }
    Run-Control $script:P16OpcodeClearBcb 0 'seed-clear-bcb' | Out-Null
    Invoke-P16OrdinaryResetEvidence -RunDirectory $RunDirectory -Label 'seed-confirm-v0' -WaitMilliseconds 45000 | Out-Null
    Run-Control $script:P16OpcodeInstallSlot $script:P16SlotBackup 'seed-backup-v0' | Out-Null
    Run-Control $script:P16OpcodeInstallSlot $script:P16SlotRecovery 'seed-recovery-v0' | Out-Null
    Invoke-P16FlashApp -AppBin $v1 -RunDirectory $RunDirectory -Label 'seed-internal-v1' | Out-Null
    Run-Control $script:P16OpcodeInstallSlot $script:P16SlotCandidate 'seed-candidate-v1' | Out-Null
    Invoke-P16FlashApp -AppBin $v0 -RunDirectory $RunDirectory -Label 'seed-internal-v0' | Out-Null
    $stage = Run-Control $script:P16OpcodeStageSlots 0 'seed-staged'
    Write-P16Json -Value $stage.Result -Path (Join-Path $RunDirectory 'staged.json')
    Write-Output 'P16_SEED=COMPLETE'
}
else {
    $script:P16SafeHalt = [uint32]$p.safeHalt
    Invoke-P16FlashApp -AppBin $originalApp -RunDirectory $RunDirectory -Label 'restore-current-app' | Out-Null
    Run-Control $script:P16OpcodeClearBcb 0 'restore-clear-test-bcb' | Out-Null
    Invoke-P16OrdinaryResetEvidence -RunDirectory $RunDirectory -Label 'restore-confirm-current' -WaitMilliseconds 45000 | Out-Null
    foreach ($entry in @(@('recovery', 4), @('backup', 2), @('candidate', 1))) {
        $name = [string]$entry[0]
        $image = Get-PinnedFile $p.slots.$name
        Invoke-P16FlashApp -AppBin $image -RunDirectory $RunDirectory -Label ('restore-source-' + $name) | Out-Null
        Run-Control $script:P16OpcodeInstallSlot ([uint32]$entry[1]) ('restore-slot-' + $name) | Out-Null
    }
    Invoke-P16FlashApp -AppBin $originalApp -RunDirectory $RunDirectory -Label 'restore-full-affected-app' | Out-Null
    $finalBcb = Run-Control $script:P16OpcodeSnapshot 0 'restore-final-bcb'
    if ([uint32]$finalBcb.Result.state -ne 4 -or [uint32]$finalBcb.Result.cur_vcode -ne 30313 -or
        [uint32]$finalBcb.Result.copy_phase -ne 0 -or [uint32]$finalBcb.Result.boot_try -ne 0) {
        throw 'Production BCB is not safely confirmed'
    }
    Invoke-P16BootRegionRestore -BackupBin $originalBoot -Length ([uint32]$p.bootAffectedBytes) `
        -RunDirectory $RunDirectory -Label 'restore-original-boot' | Out-Null
    Invoke-P16JLink -RunDirectory $RunDirectory -Label 'resume-production' -Lines @(
        'r', 'w4 0xE0042008, 0x00000000', 'g', 'Sleep 3000', 'qc'
    ) | Out-Null
    Write-Output 'P16_RESTORE=PROGRAMMED_REQUIRES_INDEPENDENT_READBACK'
}
