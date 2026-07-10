param(
  [Parameter(Mandatory = $true)]
  [string]$ReleaseTag,
  [string[]]$Channels = @("stable"),
  [switch]$Yes,
  [switch]$DryRun,
  [switch]$SkipBackfill,
  [switch]$SkipPublish,
  [switch]$SkipVerify,
  [switch]$SkipReadback,
  [switch]$KeepAssets,
  [switch]$AllowPartialR2,
  [switch]$Rollback,
  [string]$Repo,
  [string]$Bucket,
  [string]$AssetsDir,
  [string]$WranglerCwd,
  [string]$Env = "staging",
  [string]$Database = "trace-update-staging",
  [string]$ServiceUrl,
  [string]$BootstrapSummary,
  [string]$ReleaseNotes,
  [string]$ActorEmail,
  [int]$VerifyFromVersionCode = 31
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$nodeScript = Join-Path $scriptDir "publish-staging-release.mjs"

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
  throw "Node.js is required."
}

$nodeArgs = @($nodeScript, "--release-tag", $ReleaseTag)

if ($Channels.Count -gt 0) {
  $nodeArgs += "--channels"
  $nodeArgs += ($Channels -join ",")
}
if ($Yes) { $nodeArgs += "--yes" }
if ($DryRun) { $nodeArgs += "--dry-run" }
if ($SkipBackfill) { $nodeArgs += "--skip-backfill" }
if ($SkipPublish) { $nodeArgs += "--skip-publish" }
if ($SkipVerify) { $nodeArgs += "--skip-verify" }
if ($SkipReadback) { $nodeArgs += "--skip-readback" }
if ($KeepAssets) { $nodeArgs += "--keep-assets" }
if ($AllowPartialR2) { $nodeArgs += "--allow-partial-r2" }
if ($Rollback) { $nodeArgs += "--rollback" }
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
if ($WranglerCwd) {
  $nodeArgs += "--wrangler-cwd"
  $nodeArgs += $WranglerCwd
}
if ($Env) {
  $nodeArgs += "--env"
  $nodeArgs += $Env
}
if ($Database) {
  $nodeArgs += "--database"
  $nodeArgs += $Database
}
if ($ServiceUrl) {
  $nodeArgs += "--service-url"
  $nodeArgs += $ServiceUrl
}
if ($BootstrapSummary) {
  $nodeArgs += "--bootstrap-summary"
  $nodeArgs += $BootstrapSummary
}
if ($ReleaseNotes) {
  $nodeArgs += "--release-notes"
  $nodeArgs += $ReleaseNotes
}
if ($ActorEmail) {
  $nodeArgs += "--actor-email"
  $nodeArgs += $ActorEmail
}
if ($VerifyFromVersionCode -ge 0) {
  $nodeArgs += "--verify-from-version-code"
  $nodeArgs += [string]$VerifyFromVersionCode
}

& node @nodeArgs
exit $LASTEXITCODE
