$ErrorActionPreference = 'Stop'
$repository = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$initializer = Join-Path $repository 'Scripts\Initialize-EfaRuntimeSecrets.ps1'
$bootstrapper = Join-Path $repository 'Scripts\Bootstrap-EfaRuntimeSecretsFromPostgres.ps1'
$deployer = Join-Path $repository 'Scripts\Deploy-DailyBrief.ps1'
$example = Join-Path $repository 'deployment\runtime.env.example'
$compose = Join-Path $repository 'docker-compose.daily-brief.yml'

function Assert-True([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}

$initializerSource = Get-Content -LiteralPath $initializer -Raw
$bootstrapperSource = Get-Content -LiteralPath $bootstrapper -Raw
$deployerSource = Get-Content -LiteralPath $deployer -Raw
$exampleSource = Get-Content -LiteralPath $example -Raw
$composeSource = Get-Content -LiteralPath $compose -Raw
foreach ($name in 'EFA_DB_HOST', 'EFA_DB_PORT', 'EFA_DB_NAME', 'EFA_DB_USER', 'EFA_DB_PASSWORD') {
    Assert-True ($initializerSource.Contains($name) -and $bootstrapperSource.Contains($name) -and $deployerSource.Contains($name) -and $exampleSource.Contains("$name=") -and $composeSource.Contains(('${' + $name + '}'))) "Missing runtime contract: $name"
}
Assert-True ($initializerSource.Contains('Read-Host') -and $initializerSource.Contains('-AsSecureString')) 'Password input must be interactive and masked.'
Assert-True ($initializerSource.Contains('Set-Acl') -and $initializerSource.Contains('SetAccessRuleProtection')) 'Local secret file requires restricted ACLs.'
Assert-True ($bootstrapperSource.Contains('POSTGRES_PASSWORD') -and $bootstrapperSource.Contains('2>$null') -and $bootstrapperSource.Contains('Refusing to overwrite')) 'Bootstrapper must transfer the runtime password silently and fail safe.'
Assert-True ($deployerSource.Contains('--env-file') -and $deployerSource.Contains('--no-deps') -and $deployerSource.Contains('efa-daily-brief')) 'Deployment must target only Daily Brief with explicit env-file.'
Assert-True ($composeSource.Contains('efa-tools') -and -not $composeSource.Contains('ports:')) 'Daily Brief must retain the private network and no host port.'
Assert-True (-not $exampleSource.Contains('EFA_DB_PASSWORD=postgres')) 'Example must not include a secret value.'

$missingPath = Join-Path ([System.IO.Path]::GetTempPath()) ("efa-missing-{0}.env" -f [guid]::NewGuid())
try {
    & $deployer -RuntimeEnvPath $missingPath -ComposeFile (Join-Path $repository 'docker-compose.daily-brief.yml') | Out-Null
    throw 'Missing env file did not fail safe.'
}
catch {
    Assert-True ($_.Exception.Message -match 'Runtime env file is missing') 'Missing env file must fail before Docker replacement.'
}

Write-Output 'Runtime secret deployment static checks passed.'
