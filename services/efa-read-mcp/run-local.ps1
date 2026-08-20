[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$serviceRoot = $PSScriptRoot
$secretPath = Join-Path $env:USERPROFILE '.efa-os\secrets\efa-read-mcp.env'
$pythonPath = Join-Path $serviceRoot '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $secretPath -PathType Leaf)) {
    Write-Error 'The protected EFA Read MCP credential file is unavailable.'
    exit 2
}

if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    Write-Error 'The isolated EFA Read MCP Python environment is unavailable.'
    exit 3
}

$credentialLines = @(
    [System.IO.File]::ReadAllLines($secretPath) |
        Where-Object { $_.Trim() -and -not $_.TrimStart().StartsWith('#') }
)
if ($credentialLines.Count -ne 1) {
    Write-Error 'The EFA Read MCP credential file must contain exactly one setting.'
    exit 4
}

$separator = $credentialLines[0].IndexOf('=')
if ($separator -lt 1) {
    Write-Error 'The EFA Read MCP credential file format is invalid.'
    exit 4
}

$variableName = $credentialLines[0].Substring(0, $separator).Trim()
$credentialValue = $credentialLines[0].Substring($separator + 1).Trim()
if ($variableName -cne 'DATABASE_URL' -or -not $credentialValue) {
    Write-Error 'The EFA Read MCP credential file must define only DATABASE_URL.'
    exit 4
}

$hadDatabaseUrl = Test-Path Env:DATABASE_URL
$previousDatabaseUrl = $env:DATABASE_URL
$locationChanged = $false
$processExitCode = 1

try {
    $env:DATABASE_URL = $credentialValue
    Push-Location -LiteralPath $serviceRoot
    $locationChanged = $true
    & $pythonPath -m efa_read_mcp
    $processExitCode = $LASTEXITCODE
}
finally {
    if ($locationChanged) {
        Pop-Location
    }
    if ($hadDatabaseUrl) {
        $env:DATABASE_URL = $previousDatabaseUrl
    }
    else {
        Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
    }
    $credentialValue = $null
    $credentialLines = $null
}

exit $processExitCode
