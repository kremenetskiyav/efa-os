[CmdletBinding()]
param(
    [string]$RuntimeEnvPath = (Join-Path $env:USERPROFILE '.efa-os\secrets\runtime.env'),
    [string]$PostgresContainer = 'efa-postgres'
)

$ErrorActionPreference = 'Stop'
$requiredNames = @('EFA_DB_HOST', 'EFA_DB_PORT', 'EFA_DB_NAME', 'EFA_DB_USER', 'EFA_DB_PASSWORD')

if (Test-Path -LiteralPath $RuntimeEnvPath) {
    throw 'Runtime env file already exists. Refusing to overwrite it.'
}
if ((& docker inspect $PostgresContainer --format '{{.State.Running}}' 2>$null).Trim() -ne 'true') {
    throw 'PostgreSQL runtime container is unavailable.'
}

$identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$directory = Split-Path -Parent $RuntimeEnvPath
New-Item -ItemType Directory -Path $directory -Force | Out-Null
$directoryAcl = New-Object System.Security.AccessControl.DirectorySecurity
$directoryAcl.SetAccessRuleProtection($true, $false)
$directoryAcl.AddAccessRule((New-Object System.Security.AccessControl.FileSystemAccessRule($identity, 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow')))
Set-Acl -LiteralPath $directory -AclObject $directoryAcl

# Docker captures stdout locally. These values are never written to terminal,
# logs, Git, or workflow data.
$databaseName = (& docker exec $PostgresContainer sh -c 'printf "%s" "$POSTGRES_DB"' 2>$null).Trim()
$databaseUser = (& docker exec $PostgresContainer sh -c 'printf "%s" "$POSTGRES_USER"' 2>$null).Trim()
$databasePassword = (& docker exec $PostgresContainer sh -c 'printf "%s" "$POSTGRES_PASSWORD"' 2>$null)

try {
    if ([string]::IsNullOrWhiteSpace($databaseName) -or [string]::IsNullOrWhiteSpace($databaseUser) -or [string]::IsNullOrWhiteSpace($databasePassword)) {
        throw 'PostgreSQL runtime contract is incomplete.'
    }
    $lines = @(
        'EFA_DB_HOST=efa-postgres',
        'EFA_DB_PORT=5432',
        "EFA_DB_NAME=$databaseName",
        "EFA_DB_USER=$databaseUser",
        "EFA_DB_PASSWORD=$databasePassword"
    )
    [System.IO.File]::WriteAllLines($RuntimeEnvPath, $lines, (New-Object System.Text.UTF8Encoding($false)))
}
finally {
    $databasePassword = $null
}

$fileAcl = New-Object System.Security.AccessControl.FileSecurity
$fileAcl.SetAccessRuleProtection($true, $false)
$fileAcl.AddAccessRule((New-Object System.Security.AccessControl.FileSystemAccessRule($identity, 'FullControl', 'Allow')))
Set-Acl -LiteralPath $RuntimeEnvPath -AclObject $fileAcl

$names = @(Get-Content -LiteralPath $RuntimeEnvPath | Where-Object { $_ -match '^[A-Z0-9_]+=' } | ForEach-Object { ($_ -split '=', 2)[0] })
if (($requiredNames | Where-Object { $_ -notin $names }).Count -ne 0) {
    throw 'Runtime env validation failed.'
}

Write-Output 'Local runtime.env created and validated. Secret values were not displayed.'
