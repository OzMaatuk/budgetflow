# BudgetFlow Service Installation Script
# Run as Administrator

$ErrorActionPreference = "Stop"

Write-Host "BudgetFlow Service Installer" -ForegroundColor Green
Write-Host "=============================" -ForegroundColor Green
Write-Host ""

# Check if running as administrator
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
$isAdmin = $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "ERROR: This script must be run as Administrator" -ForegroundColor Red
    Write-Host "Please right-click and select 'Run as Administrator'" -ForegroundColor Yellow
    pause
    exit 1
}

# Get script directory
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$exePath = Join-Path $scriptDir "BudgetFlow.exe"
$xmlPath = Join-Path $scriptDir "task_scheduler.xml"

# Check if EXE exists
if (-not (Test-Path $exePath)) {
    Write-Host "ERROR: BudgetFlow.exe not found at: $exePath" -ForegroundColor Red
    pause
    exit 1
}

# Check if XML exists
if (-not (Test-Path $xmlPath)) {
    Write-Host "ERROR: task_scheduler.xml not found at: $xmlPath" -ForegroundColor Red
    pause
    exit 1
}

Write-Host "Installing BudgetFlow service..." -ForegroundColor Cyan

# Copy EXE to Program Files
$installDir = "C:\Program Files\BudgetFlow"
Write-Host "Creating installation directory: $installDir"

if (-not (Test-Path $installDir)) {
    New-Item -ItemType Directory -Path $installDir -Force | Out-Null
}

Write-Host "Copying executable..."
Copy-Item $exePath -Destination $installDir -Force

# Update XML with correct path
$xmlContent = Get-Content $xmlPath -Raw
$xmlContent = $xmlContent -replace 'C:\\Program Files\\BudgetFlow\\BudgetFlow\.exe', (Join-Path $installDir "BudgetFlow.exe")
$tempXmlPath = Join-Path $env:TEMP "budgetflow_task.xml"
$xmlContent | Set-Content $tempXmlPath -Force

# Register scheduled task
Write-Host "Registering scheduled task..."
try {
    # Remove existing task if present
    $existingTask = Get-ScheduledTask -TaskName "BudgetFlow" -ErrorAction SilentlyContinue
    if ($existingTask) {
        Write-Host "Removing existing task..."
        Unregister-ScheduledTask -TaskName "BudgetFlow" -Confirm:$false
    }
    
    # Register new task
    Register-ScheduledTask -Xml (Get-Content $tempXmlPath | Out-String) -TaskName "BudgetFlow" -Force | Out-Null
    
    Write-Host ""
    Write-Host "Installation complete!" -ForegroundColor Green
    Write-Host ""
    Write-Host "The BudgetFlow service will start automatically on system boot." -ForegroundColor Cyan
    Write-Host "To start it now, run: Start-ScheduledTask -TaskName 'BudgetFlow'" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "To view logs, check: %LOCALAPPDATA%\BudgetFlow\logs\service.log" -ForegroundColor Yellow
    
} catch {
    Write-Host "ERROR: Failed to register scheduled task: $_" -ForegroundColor Red
    exit 1
} finally {
    # Cleanup temp file
    if (Test-Path $tempXmlPath) {
        Remove-Item $tempXmlPath -Force
    }
}

Write-Host ""
Write-Host "Press any key to exit..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
