# Register the OpenTransit H-1 daily refresh (06:30 local) for the current user and disable the
# fetch-only task it replaces. Run once in PowerShell from the frozen export, for example:
#   powershell -ExecutionPolicy Bypass -File D:\ot\src-<commit>\deploy\aws\scheduler\register-task.ps1
# Re-running replaces the task (for a newer frozen export). Undo:
#   Unregister-ScheduledTask -TaskName 'OpenTransit H-1 daily refresh' -Confirm:$false
#   Enable-ScheduledTask -TaskName 'OpenTransit daily feed fetch'
$wrapper = Join-Path $PSScriptRoot 'daily-refresh.cmd'
$action = New-ScheduledTaskAction -Execute $wrapper
$trigger = New-ScheduledTaskTrigger -Daily -At '06:30'
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 3) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName 'OpenTransit H-1 daily refresh' -Action $action -Trigger $trigger `
    -Settings $settings -Force `
    -Description 'OpenTransit H-1 refresh: fetch, validate, build if changed, probe, publish/push, ALB probe, prune --dry-run. Logs in D:\ot\logs; see docs/operations.md.' |
    Select-Object TaskName, State
if (Get-ScheduledTask -TaskName 'OpenTransit daily feed fetch' -ErrorAction SilentlyContinue) {
    Disable-ScheduledTask -TaskName 'OpenTransit daily feed fetch' | Select-Object TaskName, State
}
Get-ScheduledTask -TaskName 'OpenTransit H-1 daily refresh' | Get-ScheduledTaskInfo | Select-Object NextRunTime
