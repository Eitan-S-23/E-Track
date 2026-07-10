param(
  [Parameter(Mandatory = $true)]
  [string]$ReleaseTag,
  [switch]$Yes,
  [switch]$DryRun,
  [switch]$SkipDownload,
  [switch]$SkipUpload,
  [switch]$SkipReadback,
  [switch]$SkipRegister,
  [switch]$KeepAssets,
  [string]$Repo,
  [string]$Bucket,
  [string]$AssetsDir,
  [string]$Output,
  [string]$WranglerCwd,
  [string]$Env,
  [string]$CommitSha,
  [string]$RunId,
  [string]$ServiceUrl,
  [string]$BootstrapSummary
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$nodeScript = Join-Path $scriptDir "backfill-r2-release.mjs"

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
  throw "Node.js is required. Install Node.js 24 or use the same version configured in GitHub Actions."
}

$nodeArgs = @($nodeScript, "--release-tag", $ReleaseTag)
if ($Yes) { $nodeArgs += "--yes" }
if ($DryRun) { $nodeArgs += "--dry-run" }
if ($SkipDownload) { $nodeArgs += "--skip-download" }
if ($SkipUpload) { $nodeArgs += "--skip-upload" }
if ($SkipReadback) { $nodeArgs += "--skip-readback" }
if ($SkipRegister) { $nodeArgs += "--skip-register" }
if ($KeepAssets) { $nodeArgs += "--keep-assets" }
if ($Repo) {
  $nodeArgs += "--repo"
  $nodeArgs += $Repo
}
if ($Bucket) {
  $nodeArgs += "--bucket"
  $nodeArgs += $Bucket
}
if ($AssetsDir) {
  $nodeArgs += "--assets-dir"
  $nodeArgs += $AssetsDir
}
if ($Output) {
  $nodeArgs += "--output"
  $nodeArgs += $Output
}
if ($WranglerCwd) {
  $nodeArgs += "--wrangler-cwd"
  $nodeArgs += $WranglerCwd
}
if ($Env) {
  $nodeArgs += "--env"
  $nodeArgs += $Env
}
if ($CommitSha) {
  $nodeArgs += "--commit-sha"
  $nodeArgs += $CommitSha
}
if ($RunId) {
  $nodeArgs += "--run-id"
  $nodeArgs += $RunId
}
if ($ServiceUrl) {
  $nodeArgs += "--service-url"
  $nodeArgs += $ServiceUrl
}
if ($BootstrapSummary) {
  $nodeArgs += "--bootstrap-summary"
  $nodeArgs += $BootstrapSummary
}

& node @nodeArgs
exit $LASTEXITCODE
