[CmdletBinding()]
param(
    [string]$TaskName = 'EFA OS - Gmail Information Polling v0.1'
)

$repository = Split-Path -Parent $PSScriptRoot
$scriptPath = Join-Path $PSScriptRoot 'Run-GmailInformationPolling.ps1'
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`" -Days 2"
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(5) `
    -RepetitionInterval (New-TimeSpan -Hours 1) `
    -RepetitionDuration (New-TimeSpan -Days 3650)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Description 'Read-only Ozon Gmail Information Intelligence polling, 48-hour overlap.' -Force | Out-Null
Write-Output "Registered: $TaskName"
