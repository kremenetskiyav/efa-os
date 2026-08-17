[CmdletBinding()]
param(
    [ValidateRange(1, 30)]
    [int]$Days = 2
)

$repository = Split-Path -Parent $PSScriptRoot
$mutex = [System.Threading.Mutex]::new($false, 'Global\EfaOsGmailInformationPollingV1')
if (-not $mutex.WaitOne(0)) {
    Write-Output 'Gmail polling already running; no concurrent collection started.'
    exit 0
}

try {
    Set-Location -LiteralPath $repository
    # The Python adapter runs on the Windows host; do not edit protected runtime.env.
    $env:EFA_DB_HOST = '127.0.0.1'
    $env:PYTHONUTF8 = '1'
    & python -X utf8 -m services.information_intelligence.gmail_polling --days $Days
    if ($LASTEXITCODE -ne 0) {
        throw "Gmail polling failed with exit code $LASTEXITCODE"
    }
}
finally {
    $mutex.ReleaseMutex() | Out-Null
    $mutex.Dispose()
}
