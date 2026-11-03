[CmdletBinding()]
param([Parameter(Mandatory = $true)][string]$Out)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '../../Tools/jlink/p1-6-common.ps1')
$Out = New-WorktreeDirectory -RepoRoot $script:P1RepoRoot -DirectoryPath $Out
$script:P16SafeHalt = [uint32]0x080410C8
$script:P16ExpectedVtor = [uint32]0x08010800
$script:Scenario = ''
$script:Calls = New-Object System.Collections.Generic.List[object]

function Invoke-P16JLink {
    param([string[]]$Lines, [string]$RunDirectory, [string]$Label, [int]$TimeoutSeconds = 120)
    $script:Calls.Add(@($Lines))
    foreach ($line in $Lines) {
        if ($line -match '^savebin "([^"]+)", 0x([0-9A-Fa-f]+), 0x([0-9A-Fa-f]+)$') {
            $path = $Matches[1]
            $address = [Convert]::ToUInt32($Matches[2], 16)
            $bytes = New-Object byte[] ([Convert]::ToInt32($Matches[3], 16))
            if ($address -eq 0xE0002000L) {
                if ($Label -notlike '*-clear-owned' -or $script:Scenario -eq 'uncleared') {
                    [BitConverter]::GetBytes([uint32]0x480410C9).CopyTo($bytes, 8)
                }
                if ($script:Scenario -eq 'foreign') { [BitConverter]::GetBytes([uint32]0x48042001).CopyTo($bytes, 12) }
            }
            if ($address -eq 0xE000EDF0L -and $script:Scenario -ne 'running') {
                [BitConverter]::GetBytes([uint32]0x20000).CopyTo($bytes, 0)
            }
            if ($address -eq 0x4002C434 -and $script:Scenario -eq 'sd-busy') {
                [BitConverter]::GetBytes([uint32]0x1000).CopyTo($bytes, 0)
            }
            [IO.File]::WriteAllBytes($path, $bytes)
        }
    }
    $pc = if ($script:Scenario -eq 'wrong-pc') { '08042000' } else { '080410C8' }
    $log = Join-Path $RunDirectory ($Label + '.log')
    [IO.File]::WriteAllText($log, "PC = $pc`nE000ED08 = 08010800`nE000ED28 = 00000000`n")
    return $log
}

$passed = 0
foreach ($case in @('pass', 'sd-busy', 'running', 'wrong-pc', 'foreign', 'uncleared')) {
    $script:Scenario = $case
    $script:Calls.Clear()
    $folder = New-WorktreeDirectory -RepoRoot $script:P1RepoRoot -DirectoryPath (Join-Path $Out $case)
    $failed = $false
    try { Invoke-P16IdleHalt -Address $script:P16SafeHalt -RunDirectory $folder -Label 'idle' | Out-Null }
    catch { $failed = $true; if ($case -eq 'pass') { throw } }
    if (($case -eq 'pass') -eq $failed) { throw "Incorrect idle-halt classification: $case" }
    $expectedCalls = if ($case -in @('pass', 'uncleared')) { 2 } else { 1 }
    if ($script:Calls.Count -ne $expectedCalls) { throw "Unexpected native action after failed gate: $case" }
    $passed++
}
$script:Scenario = 'pass'
$script:Calls.Clear()
$folder = New-WorktreeDirectory -RepoRoot $script:P1RepoRoot -DirectoryPath (Join-Path $Out 'reset')
Invoke-P16OrdinaryResetEvidence -RunDirectory $folder -Label 'normal' -WaitMilliseconds 45000 | Out-Null
$first = @($script:Calls[0])
if ($first[0] -ne 'r' -or $first[1] -ne 'w4 0xE0042008, 0x00001000' -or
    $first -contains 'h' -or @($script:Calls[1])[-1] -ne 'qc') {
    throw 'Ordinary reset must use the idle breakpoint and leave the core halted'
}
$passed++
Write-Output "P16_IDLE_HALT_MOCK_CHECKS=$passed PASS deviceOperations=0"
