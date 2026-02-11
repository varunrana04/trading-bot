# Build script for Windows (PowerShell)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Trading Engine C++ Build Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check prerequisites
Write-Host "[1/5] Checking prerequisites..." -ForegroundColor Yellow

# Check for Python
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Python not found. Please install Python 3.8+." -ForegroundColor Red
    exit 1
}
Write-Host "  Python: $pythonVersion" -ForegroundColor Green

# Check for CMake
$cmakeVersion = cmake --version 2>&1 | Select-Object -First 1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: CMake not found. Please install CMake 3.15+." -ForegroundColor Red
    Write-Host "  Download from: https://cmake.org/download/" -ForegroundColor Yellow
    exit 1
}
Write-Host "  CMake: $cmakeVersion" -ForegroundColor Green

# Check for pybind11
Write-Host "[2/5] Checking pybind11..." -ForegroundColor Yellow
$pybind11Check = pip show pybind11 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  Installing pybind11..." -ForegroundColor Yellow
    pip install pybind11
}
Write-Host "  pybind11: Installed" -ForegroundColor Green

# Navigate to cpp_engine directory
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$cppEngineDir = Join-Path $scriptDir "..\cpp_engine"

if (-not (Test-Path $cppEngineDir)) {
    Write-Host "ERROR: cpp_engine directory not found at $cppEngineDir" -ForegroundColor Red
    exit 1
}

Set-Location $cppEngineDir
Write-Host "[3/5] Building in: $cppEngineDir" -ForegroundColor Yellow

# Create build directory
$buildDir = Join-Path $cppEngineDir "build"
if (Test-Path $buildDir) {
    Write-Host "  Cleaning existing build directory..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force $buildDir
}
New-Item -ItemType Directory -Path $buildDir | Out-Null
Set-Location $buildDir

# Configure with CMake
Write-Host "[4/5] Configuring with CMake..." -ForegroundColor Yellow

# Detect Visual Studio version
$vsVersion = ""
if (Test-Path "C:\Program Files\Microsoft Visual Studio\2022") {
    $vsVersion = "Visual Studio 17 2022"
}
elseif (Test-Path "C:\Program Files (x86)\Microsoft Visual Studio\2019") {
    $vsVersion = "Visual Studio 16 2019"
}
else {
    # Try to find BuildTools 2019
    $buildToolsPath = Get-ChildItem "C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools" -ErrorAction SilentlyContinue
    if ($buildToolsPath) {
        $vsVersion = "Visual Studio 16 2019"
    }
    else {
        Write-Host "  No Visual Studio found, trying default generator..." -ForegroundColor Yellow
    }
}

# Setup CMake arguments
if ($vsVersion) {
    Write-Host "  Using: $vsVersion" -ForegroundColor Green
    $cmakeArgs = @("..", "-G", $vsVersion, "-A", "x64")
}
else {
    $cmakeArgs = @("..")
}

# Try to find pybind11 cmake dir
$pybind11Dir = python -c "import pybind11; print(pybind11.get_cmake_dir())" 2>&1
if ($LASTEXITCODE -eq 0) {
    $cmakeArgs += "-Dpybind11_DIR=$pybind11Dir"
}

# Run CMake configure
cmake @cmakeArgs 2>&1 | ForEach-Object { Write-Host "  $_" }
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: CMake configuration failed." -ForegroundColor Red
    Write-Host "  Make sure Visual Studio with C++ workload is installed." -ForegroundColor Yellow
    exit 1
}

# Build
Write-Host "[5/5] Building (Release)..." -ForegroundColor Yellow
cmake --build . --config Release 2>&1 | ForEach-Object { Write-Host "  $_" }
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Build failed." -ForegroundColor Red
    exit 1
}

# Copy the built module
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Build Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$outputFile = Get-ChildItem -Path $buildDir -Recurse -Filter "trading_engine*.pyd" | Select-Object -First 1
if ($outputFile) {
    $destDir = Join-Path $scriptDir "..\cpp_engine"
    Copy-Item $outputFile.FullName -Destination $destDir -Force
    Write-Host "Module copied to: $destDir\$($outputFile.Name)" -ForegroundColor Green
    Write-Host ""
    Write-Host "To test the module:" -ForegroundColor Yellow
    Write-Host "  cd $destDir" -ForegroundColor Cyan
    Write-Host "  python -c `"from trading_engine import *; print('Success!')`"" -ForegroundColor Cyan
}
else {
    Write-Host "WARNING: Could not find built .pyd file." -ForegroundColor Yellow
    Write-Host "Check the build output above for errors." -ForegroundColor Yellow
}
