# BudgetFlow Build Script
# Usage: .\build.ps1 [-Clean] [-CleanAll] [-Release]

param(
    [switch]$Clean,
    [switch]$CleanAll,
    [switch]$Release
)

$ErrorActionPreference = "Stop"

Write-Host "BudgetFlow Build Script" -ForegroundColor Green
Write-Host "=======================" -ForegroundColor Green
Write-Host ""

# Clean if requested
if ($Clean -or $CleanAll) {
    Write-Host "Cleaning build artifacts..." -ForegroundColor Cyan
    
    if (Test-Path "venv") {
        Write-Host "  Removing venv..." -ForegroundColor Yellow
        Remove-Item -Recurse -Force "venv"
    }
    
    Write-Host "  Removing __pycache__..." -ForegroundColor Yellow
    Get-ChildItem -Path . -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    Get-ChildItem -Path . -Recurse -Filter "*.pyc" | Remove-Item -Force -ErrorAction SilentlyContinue
    
    if (Test-Path "build") {
        Write-Host "  Removing build..." -ForegroundColor Yellow
        Remove-Item -Recurse -Force "build"
    }
    
    if (Test-Path "dist") {
        Write-Host "  Removing dist..." -ForegroundColor Yellow
        Remove-Item -Recurse -Force "dist"
    }
    
    if (Test-Path "release") {
        Write-Host "  Removing release..." -ForegroundColor Yellow
        Remove-Item -Recurse -Force "release"
    }
    
    Write-Host "Clean complete!" -ForegroundColor Green
    Write-Host ""
}

# Clean user data if CleanAll requested
if ($CleanAll) {
    $configPath = "$env:LOCALAPPDATA\BudgetFlow"
    if (Test-Path $configPath) {
        Write-Host "Cleaning user configuration..." -ForegroundColor Cyan
        Write-Host "  Removing $configPath..." -ForegroundColor Yellow
        Remove-Item -Recurse -Force $configPath
        Write-Host "User data cleaned!" -ForegroundColor Green
        Write-Host ""
    }
}

# Check Python
try {
    $pythonVersion = python --version
    Write-Host "Python found: $pythonVersion" -ForegroundColor Cyan
} catch {
    Write-Host "ERROR: Python not found. Install Python 3.11+" -ForegroundColor Red
    exit 1
}

# Create/activate venv
if (-not (Test-Path "venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Cyan
    python -m venv venv
}

Write-Host "Activating virtual environment..." -ForegroundColor Cyan
& .\venv\Scripts\Activate.ps1

# Install dependencies
Write-Host "Installing dependencies..." -ForegroundColor Cyan
python -m pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
pip install pyinstaller --quiet

Write-Host "Dependencies installed!" -ForegroundColor Green

# Build executable
Write-Host ""
Write-Host "Building executable..." -ForegroundColor Cyan
pyinstaller budgetflow.spec --clean

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Build failed!" -ForegroundColor Red
    exit 1
}

# Copy resources to dist
Write-Host "Copying resources..." -ForegroundColor Cyan
Copy-Item -Path "resources" -Destination "dist\resources" -Recurse -Force
Copy-Item -Path "service\install_service.ps1" -Destination "dist\install_service.ps1" -Force
Copy-Item -Path "service\task_scheduler.xml" -Destination "dist\task_scheduler.xml" -Force
Copy-Item -Path "README.md" -Destination "dist\README.md" -Force

# Create FIRST_RUN.txt
@"
BudgetFlow - Quick Start
=========================

1. Run BudgetFlow.exe
2. Setup wizard appears - enter your credentials:
   - Gemini API Key: https://aistudio.google.com/app/apikey
   - Google Service Account JSON file
   - Google Drive folder ID
3. Click "Validate & Save"

Logs: %LOCALAPPDATA%\BudgetFlow\logs\service.log
See README.md for details
"@ | Out-File -FilePath "dist\FIRST_RUN.txt" -Encoding UTF8

Write-Host ""
Write-Host "Build successful!" -ForegroundColor Green
Write-Host "Output: dist\BudgetFlow.exe" -ForegroundColor Cyan

# Create release package if requested
if ($Release) {
    Write-Host ""
    Write-Host "Creating release package..." -ForegroundColor Cyan
    
    # Get version
    $version = "1.0.0"
    if (Test-Path "version_info.txt") {
        $versionContent = Get-Content "version_info.txt" -Raw
        if ($versionContent -match "FileVersion', '([^']+)'") {
            $version = $matches[1]
        }
    }
    
    # Create release folder
    $releaseFolder = "release\BudgetFlow-v$version"
    if (Test-Path "release") {
        Remove-Item "release" -Recurse -Force
    }
    New-Item -ItemType Directory -Path $releaseFolder -Force | Out-Null
    
    # Copy files
    Copy-Item "dist\BudgetFlow.exe" -Destination $releaseFolder
    Copy-Item "dist\resources" -Destination "$releaseFolder\resources" -Recurse -Force
    Copy-Item "dist\install_service.ps1" -Destination $releaseFolder
    Copy-Item "dist\task_scheduler.xml" -Destination $releaseFolder
    Copy-Item "dist\README.md" -Destination $releaseFolder
    Copy-Item "dist\FIRST_RUN.txt" -Destination $releaseFolder
    
    # Create ZIP
    $zipPath = "release\BudgetFlow-v$version-Windows-x64.zip"
    Compress-Archive -Path "$releaseFolder\*" -DestinationPath $zipPath -Force
    
    $zipSize = [math]::Round((Get-Item $zipPath).Length / 1MB, 2)
    
    Write-Host ""
    Write-Host "Release package created!" -ForegroundColor Green
    Write-Host "Package: $zipPath ($zipSize MB)" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Upload to GitHub Releases" -ForegroundColor Yellow
}

Write-Host ""
