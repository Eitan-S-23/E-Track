param(
  [switch]$Yes,
  [switch]$DryRun,
  [switch]$SkipCheck,
  [switch]$SkipSecrets,
  [switch]$SkipDeploy,
  [string]$ProjectName,
  [string]$Branch
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$nodeScript = Join-Path $scriptDir "deploy-admin-staging.mjs"

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
  throw "Node.js is required. Install Node.js 24 or use the same version configured in GitHub Actions."
}

$nodeArgs = @($nodeScript)
if ($Yes) { $nodeArgs += "--yes" }
if ($DryRun) { $nodeArgs += "--dry-run" }
if ($SkipCheck) { $nodeArgs += "--skip-check" }
if ($SkipSecrets) { $nodeArgs += "--skip-secrets" }
if ($SkipDeploy) { $nodeArgs += "--skip-deploy" }
if ($ProjectName) {
  $nodeArgs += "--project-name"
  $nodeArgs += $ProjectName
}
if ($Branch) {
  $nodeArgs += "--branch"
  $nodeArgs += $Branch
}

& node @nodeArgs
exit $LASTEXITCODE
