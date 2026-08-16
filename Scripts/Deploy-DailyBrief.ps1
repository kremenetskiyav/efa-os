[CmdletBinding()]
param(
    [string]$RuntimeEnvPath = (Join-Path $env:USERPROFILE '.efa-os\secrets\runtime.env'),
    [string]$ComposeFile = (Join-Path $PSScriptRoot '..\docker-compose.daily-brief.yml')
)

$ErrorActionPreference = 'Stop'
$requiredNames = @('EFA_DB_HOST', 'EFA_DB_PORT', 'EFA_DB_NAME', 'EFA_DB_USER', 'EFA_DB_PASSWORD')
$service = 'efa-daily-brief'

if (-not (Test-Path -LiteralPath $RuntimeEnvPath -PathType Leaf)) {
    throw 'Runtime env file is missing. Run Initialize-EfaRuntimeSecrets.ps1 first.'
}
if (-not (Test-Path -LiteralPath $ComposeFile -PathType Leaf)) {
    throw 'Daily Brief compose file is missing.'
}

$values = @{}
foreach ($line in Get-Content -LiteralPath $RuntimeEnvPath) {
    if ($line -match '^([A-Z0-9_]+)=(.*)$') { $values[$matches[1]] = $matches[2] }
}
foreach ($name in $requiredNames) {
    if (-not $values.ContainsKey($name) -or [string]::IsNullOrWhiteSpace($values[$name])) {
        throw "Runtime env is missing required variable name: $name"
    }
}
if ($values['EFA_DB_HOST'] -ne 'efa-postgres' -or $values['EFA_DB_PORT'] -ne '5432') {
    throw 'Runtime env must use efa-postgres:5432 for private Docker access.'
}

$oldImageId = (& docker inspect $service --format '{{.Image}}' 2>$null).Trim()
$imageRef = (& docker inspect $service --format '{{.Config.Image}}' 2>$null).Trim()
if ([string]::IsNullOrWhiteSpace($oldImageId) -or [string]::IsNullOrWhiteSpace($imageRef)) {
    throw 'Existing Daily Brief container is unavailable; refusing replacement without rollback image.'
}
$rollbackRef = "efa-daily-brief:rollback-$([DateTime]::UtcNow.ToString('yyyyMMddHHmmss'))"
& docker image tag $oldImageId $rollbackRef

function Restore-DailyBrief {
    & docker image tag $rollbackRef $imageRef
    & docker compose --env-file $RuntimeEnvPath -f $ComposeFile up -d --no-deps --force-recreate $service
}

try {
    & docker compose --env-file $RuntimeEnvPath -f $ComposeFile up -d --build --no-deps --force-recreate $service
    if ($LASTEXITCODE -ne 0) { throw 'Docker Compose deployment failed.' }
    Start-Sleep -Seconds 3
    & docker exec $service python -c "import urllib.request; response=urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=5); assert response.status == 200"
    if ($LASTEXITCODE -ne 0) { throw 'Daily Brief health check failed.' }
}
catch {
    Restore-DailyBrief
    throw
}

Write-Output 'Daily Brief deployed and health-checked. Runtime secret values were not displayed.'
