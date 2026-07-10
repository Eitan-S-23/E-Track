param(
  [string]$Config = "cloudflare/update-service/.github-actions-secrets.staging.local.json",
  [switch]$Yes,
  [switch]$DryRun,
  [switch]$SkipVerify
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..\..")).Path

function Resolve-RepoPath([string]$PathValue) {
  if ([System.IO.Path]::IsPathRooted($PathValue)) {
    return $PathValue
  }
  return Join-Path $repoRoot $PathValue
}

function Fail([string]$Message) {
  throw $Message
}

function IsBlank($Value) {
  return $null -eq $Value -or [string]::IsNullOrWhiteSpace([string]$Value)
}

function NormalizeConfigValue($Value) {
  if ($null -eq $Value) {
    return ""
  }
  $text = [string]$Value
  if ($text.Length -gt 0 -and [int][char]$text[0] -eq 0xFEFF) {
    $text = $text.Substring(1)
  }
  return $text.Trim()
}

function ObjectToHashtable($Object) {
  $map = [ordered]@{}
  if ($null -eq $Object) {
    return $map
  }
  foreach ($property in $Object.PSObject.Properties) {
    $map[$property.Name] = NormalizeConfigValue $property.Value
  }
  return $map
}

function Quote-ProcessArgument([string]$Value) {
  if ($null -eq $Value) {
    return '""'
  }
  if ($Value -notmatch '[\s"]') {
    return $Value
  }
  return '"' + ($Value -replace '"', '\"') + '"'
}

function IsTransientGhFailure([string]$ErrorText) {
  if (IsBlank $ErrorText) {
    return $false
  }
  return $ErrorText -match "(?i)(timeout|timed out|keyring|connection reset|temporarily unavailable|TLS handshake timeout|i/o timeout|EOF)"
}

function Get-GhFailureHint([string]$ErrorText) {
  if ($ErrorText -match "(?i)(keyring|Timeout trying to log in)") {
    return @"

GitHub CLI could not read the saved token from the Windows keyring.
Repair the gh login, or set GH_TOKEN in this PowerShell session to bypass the keyring:
  gh auth status --hostname github.com --active
  gh auth login --hostname github.com --web
"@
  }
  return ""
}

function Invoke-GhCapture([string[]]$Arguments, [string]$StandardInput = $null) {
  $gh = Get-Command gh -ErrorAction SilentlyContinue
  if (-not $gh) {
    Fail "GitHub CLI 'gh' is required. Install it and run 'gh auth login'."
  }

  $safeCommand = "gh " + ($Arguments -join " ")
  $maxAttempts = 3
  for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {
    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo.FileName = $gh.Source
    $process.StartInfo.Arguments = ($Arguments | ForEach-Object { Quote-ProcessArgument $_ }) -join " "
    $process.StartInfo.RedirectStandardOutput = $true
    $process.StartInfo.RedirectStandardError = $true
    $process.StartInfo.RedirectStandardInput = $null -ne $StandardInput
    if ($null -ne $StandardInput) {
      $process.StartInfo.StandardInputEncoding = [System.Text.UTF8Encoding]::new($false)
    }
    $process.StartInfo.UseShellExecute = $false

    [void]$process.Start()
    if ($null -ne $StandardInput) {
      $process.StandardInput.Write($StandardInput)
      if (-not $StandardInput.EndsWith("`n")) {
        $process.StandardInput.WriteLine()
      }
      $process.StandardInput.Close()
    }
    $stdout = $process.StandardOutput.ReadToEnd()
    $stderr = $process.StandardError.ReadToEnd()
    $process.WaitForExit()

    if ($process.ExitCode -eq 0) {
      return $stdout
    }

    if ($attempt -lt $maxAttempts -and (IsTransientGhFailure $stderr)) {
      Write-Warning "$safeCommand failed with a transient GitHub CLI error. Retrying in 2 seconds ($attempt/$maxAttempts)."
      Start-Sleep -Seconds 2
      continue
    }

    $hint = Get-GhFailureHint $stderr
    Fail "$safeCommand failed with exit code $($process.ExitCode). $stderr$hint"
  }
}

function Get-GhNames([string[]]$Arguments) {
  $json = Invoke-GhCapture $Arguments
  if (IsBlank $json) {
    return [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
  }
  $items = $json | ConvertFrom-Json
  $set = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
  foreach ($item in @($items)) {
    if (-not (IsBlank $item.name)) {
      [void]$set.Add([string]$item.name)
    }
  }
  return $set
}

function Set-GitHubSecret([string]$Repo, [string]$Name, [string]$Value) {
  Invoke-GhCapture @("secret", "set", $Name, "--repo", $Repo) $Value | Out-Null
}

function Set-GitHubVariable([string]$Repo, [string]$Name, [string]$Value) {
  Invoke-GhCapture @("variable", "set", $Name, "--repo", $Repo, "--body", $Value) | Out-Null
}

function AddIfMissing([System.Collections.Generic.List[string]]$List, [string]$Name) {
  if (-not $List.Contains($Name)) {
    $List.Add($Name)
  }
}

$configPath = Resolve-RepoPath $Config
if (-not (Test-Path -LiteralPath $configPath)) {
  $example = Join-Path $repoRoot "cloudflare/update-service/github-actions-secrets.staging.example.json"
  Fail @"
Missing config file:
  $configPath

Create it from the example, then fill the blank values:
  Copy-Item "$example" "$configPath"

The local config path is ignored by git.
"@
}

$configObject = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
$repo = [string]$configObject.repository
if (IsBlank $repo) {
  $repo = (Invoke-GhCapture @("repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner")).Trim()
}
if (IsBlank $repo) {
  Fail "Repository is missing. Set repository in the config file, for example Eitan-S-23/Trace."
}

$secrets = ObjectToHashtable $configObject.secrets
$variables = ObjectToHashtable $configObject.variables

if (IsBlank $variables["TRACE_PUBLIC_UPDATE_SERVICE_URL"]) {
  $publicUpdateUrl = [Environment]::GetEnvironmentVariable("TRACE_PUBLIC_UPDATE_SERVICE_URL")
  if (-not (IsBlank $publicUpdateUrl)) {
    $variables["TRACE_PUBLIC_UPDATE_SERVICE_URL"] = NormalizeConfigValue $publicUpdateUrl
  }
}

$useBootstrapSummary = $configObject.useBootstrapSummary -eq $true
if ($useBootstrapSummary) {
  $bootstrapSummaryPath = [string]$configObject.bootstrapSummaryPath
  if (IsBlank $bootstrapSummaryPath) {
    $bootstrapSummaryPath = "cloudflare/update-service/.bootstrap/staging-summary.json"
  }
  $bootstrapSummaryPath = Resolve-RepoPath $bootstrapSummaryPath
  if (Test-Path -LiteralPath $bootstrapSummaryPath) {
    $summary = Get-Content -LiteralPath $bootstrapSummaryPath -Raw | ConvertFrom-Json
    if ((IsBlank $secrets["TRACE_UPDATE_SERVICE_URL"]) -and -not (IsBlank $summary.githubSecrets.TRACE_UPDATE_SERVICE_URL)) {
      $secrets["TRACE_UPDATE_SERVICE_URL"] = [string]$summary.githubSecrets.TRACE_UPDATE_SERVICE_URL
    }
    if ((IsBlank $secrets["TRACE_DEPLOY_TOKEN"]) -and -not (IsBlank $summary.githubSecrets.TRACE_DEPLOY_TOKEN)) {
      $secrets["TRACE_DEPLOY_TOKEN"] = [string]$summary.githubSecrets.TRACE_DEPLOY_TOKEN
    }
    if ((IsBlank $variables["TRACE_R2_BUCKET"]) -and -not (IsBlank $summary.r2BucketName)) {
      $variables["TRACE_R2_BUCKET"] = [string]$summary.r2BucketName
    }
  } else {
    Write-Warning "Bootstrap summary not found: $bootstrapSummaryPath"
  }
}

$requiredSecrets = [System.Collections.Generic.List[string]]::new()
foreach ($name in @(
  "TRACE_UPDATE_SERVICE_URL",
  "TRACE_DEPLOY_TOKEN",
  "CLOUDFLARE_ACCOUNT_ID",
  "CLOUDFLARE_API_TOKEN"
)) {
  AddIfMissing $requiredSecrets $name
}

if ($configObject.requireAndroidSigning -ne $false) {
  foreach ($name in @(
    "ANDROID_RELEASE_KEYSTORE_BASE64",
    "ANDROID_RELEASE_KEYSTORE_PASSWORD",
    "ANDROID_RELEASE_KEY_ALIAS",
    "ANDROID_RELEASE_KEY_PASSWORD"
  )) {
    AddIfMissing $requiredSecrets $name
  }
}

$requiredVariables = [System.Collections.Generic.List[string]]::new()
AddIfMissing $requiredVariables "TRACE_R2_BUCKET"
AddIfMissing $requiredVariables "TRACE_PUBLIC_UPDATE_SERVICE_URL"

if ($configObject.requirePayloadSigning -eq $true) {
  foreach ($name in @(
    "TRACE_UPDATE_PAYLOAD_ED25519_PRIVATE_KEY_BASE64",
    "TRACE_UPDATE_PAYLOAD_ED25519_PUBLIC_KEY_BASE64"
  )) {
    AddIfMissing $requiredSecrets $name
  }
  AddIfMissing $requiredVariables "TRACE_UPDATE_PAYLOAD_KEY_VERSION"
}

Invoke-GhCapture @("auth", "status", "--hostname", "github.com", "--active") | Out-Null
$existingSecrets = Get-GhNames @("secret", "list", "--repo", $repo, "--app", "actions", "--json", "name")
$existingVariables = Get-GhNames @("variable", "list", "--repo", $repo, "--json", "name")

$secretSets = [System.Collections.Generic.List[string]]::new()
$secretSkips = [System.Collections.Generic.List[string]]::new()
$missingSecrets = [System.Collections.Generic.List[string]]::new()

foreach ($name in $secrets.Keys) {
  $value = $secrets[$name]
  if (IsBlank $value) {
    if ($existingSecrets.Contains($name)) {
      $secretSkips.Add($name)
    }
    continue
  }
  $secretSets.Add($name)
}

foreach ($name in $requiredSecrets) {
  $hasLocalValue = $secrets.Contains($name) -and -not (IsBlank $secrets[$name])
  $hasRemoteName = $existingSecrets.Contains($name)
  if (-not $hasLocalValue -and -not $hasRemoteName) {
    $missingSecrets.Add($name)
  }
}

$variableSets = [System.Collections.Generic.List[string]]::new()
$variableSkips = [System.Collections.Generic.List[string]]::new()
$missingVariables = [System.Collections.Generic.List[string]]::new()

foreach ($name in $variables.Keys) {
  $value = $variables[$name]
  if (IsBlank $value) {
    if ($existingVariables.Contains($name)) {
      $variableSkips.Add($name)
    }
    continue
  }
  $variableSets.Add($name)
}

foreach ($name in $requiredVariables) {
  $hasLocalValue = $variables.Contains($name) -and -not (IsBlank $variables[$name])
  $hasRemoteName = $existingVariables.Contains($name)
  if (-not $hasLocalValue -and -not $hasRemoteName) {
    $missingVariables.Add($name)
  }
}

Write-Output "GitHub Actions secret configuration plan"
Write-Output "- Repository: $repo"
Write-Output "- Config: $configPath"
Write-Output "- Use bootstrap summary: $useBootstrapSummary"
Write-Output "- Require Android signing: $($configObject.requireAndroidSigning -ne $false)"
Write-Output "- Require payload signing: $($configObject.requirePayloadSigning -eq $true)"
Write-Output "- Secrets to set/update: $($secretSets.Count)"
foreach ($name in $secretSets) { Write-Output "  secret: $name" }
Write-Output "- Secrets already present and left unchanged: $($secretSkips.Count)"
foreach ($name in $secretSkips) { Write-Output "  secret: $name" }
Write-Output "- Variables to set/update: $($variableSets.Count)"
foreach ($name in $variableSets) { Write-Output "  variable: $name" }
Write-Output "- Variables already present and left unchanged: $($variableSkips.Count)"
foreach ($name in $variableSkips) { Write-Output "  variable: $name" }

if ($missingSecrets.Count -gt 0 -or $missingVariables.Count -gt 0) {
  if ($missingSecrets.Count -gt 0) {
    Write-Output "- Missing required secrets:"
    foreach ($name in $missingSecrets) { Write-Output "  secret: $name" }
  }
  if ($missingVariables.Count -gt 0) {
    Write-Output "- Missing required variables:"
    foreach ($name in $missingVariables) { Write-Output "  variable: $name" }
  }
  Fail "Fill the missing values in the local config file or create them in GitHub first."
}

if ($DryRun) {
  Write-Output ""
  Write-Output "Dry run only. No GitHub Secrets or Variables were changed."
  exit 0
}

if (-not $Yes) {
  Fail "Pass -Yes to write GitHub Actions Secrets and Variables."
}

foreach ($name in $secretSets) {
  Write-Output "Setting GitHub secret $name"
  Set-GitHubSecret $repo $name $secrets[$name]
}

foreach ($name in $variableSets) {
  Write-Output "Setting GitHub variable $name"
  Set-GitHubVariable $repo $name $variables[$name]
}

if (-not $SkipVerify) {
  $verifiedSecrets = Get-GhNames @("secret", "list", "--repo", $repo, "--app", "actions", "--json", "name")
  $verifiedVariables = Get-GhNames @("variable", "list", "--repo", $repo, "--json", "name")
  foreach ($name in $requiredSecrets) {
    if (-not $verifiedSecrets.Contains($name)) {
      Fail "Required secret was not found after configuration: $name"
    }
  }
  foreach ($name in $requiredVariables) {
    if (-not $verifiedVariables.Contains($name)) {
      Fail "Required variable was not found after configuration: $name"
    }
  }
}

Write-Output ""
Write-Output "GitHub Actions Secrets and Variables are configured."
