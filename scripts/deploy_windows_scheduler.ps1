# ==============================================================================
# Windows Task Scheduler Deployment Script for UPPCL Monitoring
# Runs synchronization cycle automatically every 5 minutes in background
# ==============================================================================

param (
    [int]$IntervalMinutes = 5,
    [string]$TaskName = "UPPCL_X_Complaint_Monitor",
    [switch]$Uninstall = $false
)

$ProjectRoot = (Get-Item $PSScriptRoot).Parent.FullName
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$LogDir = Join-Path $ProjectRoot "logs"

if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

if ($Uninstall) {
    Write-Host "[*] Removing scheduled task '$TaskName'..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "[+] Task '$TaskName' removed successfully." -ForegroundColor Green
    exit 0
}

if (-not (Test-Path $VenvPython)) {
    Write-Error "Virtual environment python not found at $VenvPython. Please initialize .venv first."
    exit 1
}

Write-Host "[*] Configuring Scheduled Task: '$TaskName' to run every $IntervalMinutes minutes..." -ForegroundColor Cyan

# Define Action
$ActionArgs = "-m uppcl_x_automation.cli sync"
$Action = New-ScheduledTaskAction -Execute $VenvPython -Argument $ActionArgs -WorkingDirectory $ProjectRoot

# Define Trigger (Runs every X minutes indefinitely)
$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes) -RepetitionDuration ([TimeSpan]::MaxValue)

# Define Settings
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances IgnoreNew

# Register Task
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "Monitors public UPPCL electricity complaints on X and syncs to Google Sheets." -Force | Out-Null

Write-Host "[+] Scheduled Task '$TaskName' registered successfully!" -ForegroundColor Green
Write-Host "    - Working Directory: $ProjectRoot"
Write-Host "    - Executable:        $VenvPython"
Write-Host "    - Polling Frequency: Every $IntervalMinutes minutes"
Write-Host "    - Check Status via:  Get-ScheduledTask -TaskName '$TaskName'"
