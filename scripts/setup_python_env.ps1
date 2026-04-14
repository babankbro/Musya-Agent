# PowerShell script to set up Conda environment for Musya Agent
# Usage: .\scripts\setup_python_env.ps1

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Musya Agent - Conda Environment Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check Conda installation
Write-Host "[1/6] Checking Conda installation..." -ForegroundColor Yellow
$condaVersion = conda --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Conda not found. Please install Anaconda or Miniconda" -ForegroundColor Red
    Write-Host "  Download from: https://docs.conda.io/en/latest/miniconda.html" -ForegroundColor Yellow
    exit 1
}

Write-Host "  Found: $condaVersion" -ForegroundColor Green

# Check if environment.yml exists
Write-Host ""
Write-Host "[2/6] Checking environment.yml..." -ForegroundColor Yellow
if (-not (Test-Path "environment.yml")) {
    Write-Host "  ERROR: environment.yml not found" -ForegroundColor Red
    exit 1
}
Write-Host "  environment.yml found" -ForegroundColor Green

# Check if environment already exists
Write-Host ""
Write-Host "[3/6] Checking for existing environment..." -ForegroundColor Yellow
$envExists = conda env list | Select-String "musya-agent"
if ($envExists) {
    Write-Host "  Environment 'musya-agent' already exists" -ForegroundColor Yellow
    Write-Host "  Updating environment..." -ForegroundColor Yellow
    conda env update -f environment.yml --prune
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  Environment updated successfully" -ForegroundColor Green
    } else {
        Write-Host "  ERROR: Failed to update environment" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "  Creating new environment 'musya-agent'..." -ForegroundColor Yellow
    conda env create -f environment.yml
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  Environment created successfully" -ForegroundColor Green
    } else {
        Write-Host "  ERROR: Failed to create environment" -ForegroundColor Red
        exit 1
    }
}

# Activate environment
Write-Host ""
Write-Host "[4/6] Activating environment..." -ForegroundColor Yellow
Write-Host "  Note: Environment activation in PowerShell" -ForegroundColor Cyan
Write-Host "  Run: conda activate musya-agent" -ForegroundColor White

# Initialize conda for PowerShell if needed
$condaInit = conda init powershell 2>&1
Write-Host "  Conda initialized for PowerShell" -ForegroundColor Green

# Verify Python version
Write-Host ""
Write-Host "[5/6] Verifying Python version..." -ForegroundColor Yellow
conda activate musya-agent 2>&1 | Out-Null
$pythonVersion = python --version 2>&1
Write-Host "  Python version: $pythonVersion" -ForegroundColor Green

# Verify key packages
Write-Host ""
Write-Host "[6/6] Verifying key packages..." -ForegroundColor Yellow
$packages = @("fastapi", "crewai", "psycopg2", "chromadb", "minio")
$allInstalled = $true

foreach ($package in $packages) {
    $installed = pip show $package 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  $package - OK" -ForegroundColor Green
    } else {
        Write-Host "  $package - MISSING" -ForegroundColor Red
        $allInstalled = $false
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
if ($allInstalled) {
    Write-Host "SUCCESS: Conda environment ready!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "1. Activate environment: conda activate musya-agent" -ForegroundColor White
    Write-Host "2. Check database: python scripts\check_database.py" -ForegroundColor White
    Write-Host "3. Run setup test: python scripts\test_citation_setup.py" -ForegroundColor White
} else {
    Write-Host "WARNING: Some packages are missing" -ForegroundColor Yellow
    Write-Host "Try: conda env update -f environment.yml" -ForegroundColor White
}
Write-Host "========================================" -ForegroundColor Cyan
