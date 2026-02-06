# Yit Automated Installer
Write-Host "Starting Yit Setup..." -ForegroundColor Cyan

# 1. Check for Python
if (-not (Get-Command "python" -ErrorAction SilentlyContinue)) {
    Write-Error "Python is not found! Please install Python from https://www.python.org/downloads/ and try again."
    pause
    exit 1
}

# 2. Setup Virtual Environment & Dependencies
Write-Host "`n[1/3] Setting up Python environment..." -ForegroundColor Yellow

$VenvDir = Join-Path $PSScriptRoot "venv"
if (-not (Test-Path $VenvDir)) {
    Write-Host "Creating virtual environment..."
    python -m venv "$VenvDir"
}

$PipExe = Join-Path $VenvDir "Scripts\pip.exe"
if (-not (Test-Path $PipExe)) {
    Write-Error "Failed to create virtual environment (pip not found)."
    pause
    exit 1
}

# Upgrade pip and install requirements
$PythonExe = Join-Path $VenvDir "Scripts\python.exe"
$ReqFile = Join-Path $PSScriptRoot "requirements.txt"

& $PythonExe -m pip install --upgrade pip | Out-Null
& $PipExe install -r "$ReqFile"

if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to install dependencies."
    pause
    exit 1
}

# 3. Check/Install MPV
Write-Host "`n[2/3] Checking for MPV player..." -ForegroundColor Yellow
if (-not (Get-Command "mpv" -ErrorAction SilentlyContinue)) {
    Write-Host "MPV not found. Attempting to install via Winget..." -ForegroundColor Cyan
    winget install mpv.mpv
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to install MPV. Please install manually: https://mpv.io/installation/"
        # We don't exit here, maybe they have it in a weird place, but warn them.
    }
    else {
        Write-Host "MPV installed successfully!" -ForegroundColor Green
    }
}
else {
    Write-Host "MPV is already available." -ForegroundColor Green
}

# 4. Add to PATH
Write-Host "`n[3/3] Configuring System PATH..." -ForegroundColor Yellow
$CurrentDir = $PSScriptRoot
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")

if ($UserPath -notlike "*$CurrentDir*") {
    $NewPath = "$UserPath;$CurrentDir"
    [Environment]::SetEnvironmentVariable("Path", $NewPath, "User")
    Write-Host "Added '$CurrentDir' to PATH." -ForegroundColor Green
    Write-Host "NOTE: You must RESTART your terminal/PC for this to take effect." -ForegroundColor Magenta
}
else {
    Write-Host "Path already configured." -ForegroundColor Green
}

Write-Host "`nInstallation Complete! " -ForegroundColor Cyan
Write-Host "You can now type 'yit' in any new terminal window."
pause
