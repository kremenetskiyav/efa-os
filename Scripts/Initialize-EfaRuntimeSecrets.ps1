[CmdletBinding()]
param(
    [string]$RuntimeEnvPath = (Join-Path $env:USERPROFILE '.efa-os\secrets\runtime.env')
)

$ErrorActionPreference = 'Stop'
$requiredNames = @('EFA_DB_HOST', 'EFA_DB_PORT', 'EFA_DB_NAME', 'EFA_DB_USER', 'EFA_DB_PASSWORD')

if (Test-Path -LiteralPath $RuntimeEnvPath) {
    throw 'Runtime env file already exists. Refusing to overwrite it.'
}

$databaseName = Read-Host 'PostgreSQL database name'
$databaseUser = Read-Host 'PostgreSQL user'
$securePassword = Read-Host 'PostgreSQL password' -AsSecureString

if ([string]::IsNullOrWhiteSpace($databaseName) -or [string]::IsNullOrWhiteSpace($databaseUser) -or $securePassword.Length -eq 0) {
    throw 'Database name, user, and password are required.'
}

$directory = Split-Path -Parent $RuntimeEnvPath
New-Item -ItemType Directory -Path $directory -Force | Out-Null
$identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$directoryAcl = New-Object System.Security.AccessControl.DirectorySecurity
$directoryAcl.SetAccessRuleProtection($true, $false)
$directoryAcl.AddAccessRule((New-Object System.Security.AccessControl.FileSystemAccessRule($identity, 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow')))
Set-Acl -LiteralPath $directory -AclObject $directoryAcl

$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
try {
    $plainPassword = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    $lines = @(
        'EFA_DB_HOST=efa-postgres',
        'EFA_DB_PORT=5432',
        "EFA_DB_NAME=$databaseName",
        "EFA_DB_USER=$databaseUser",
        "EFA_DB_PASSWORD=$plainPassword"
    )
    [System.IO.File]::WriteAllLines($RuntimeEnvPath, $lines, (New-Object System.Text.UTF8Encoding($false)))
}
finally {
    if ($bstr -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
    $plainPassword = $null
    $securePassword.Dispose()
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
