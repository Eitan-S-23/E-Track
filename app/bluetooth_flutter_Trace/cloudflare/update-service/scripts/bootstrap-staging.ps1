param(
  [switch]$Yes,
  [switch]$DryRun,
  [switch]$SkipDeploy,
  [switch]$SkipSecrets,
  [switch]$SkipMigrations,
  [switch]$SkipSmoke,
  [string]$Output
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$nodeScript = Join-Path $scriptDir "bootstrap-staging.mjs"

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
  throw "Node.js is required. Install Node.js 24 or use the same version configured in GitHub Actions."
}

$nodeArgs = @($nodeScript, "--env", "staging")
if ($Yes) { $nodeArgs += "--yes" }
if ($DryRun) { $nodeArgs += "--dry-run" }
if ($SkipDeploy) { $nodeArgs += "--skip-deploy" }
if ($SkipSecrets) { $nodeArgs += "--skip-secrets" }
if ($SkipMigrations) { $nodeArgs += "--skip-migrations" }
if ($SkipSmoke) { $nodeArgs += "--skip-smoke" }
if ($Output) {
  $nodeArgs += "--output"
  $nodeArgs += $Output
}

& node @nodeArgs
exit $LASTEXITCODE
