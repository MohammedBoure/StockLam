param(
    [string]$PythonPath = "",
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

if (-not $PythonPath) {
    $PyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($PyLauncher) {
        $PythonPath = (& py -3.12 -c "import sys; print(sys.executable)").Trim()
    }
}

if (-not $PythonPath) {
    throw "Python 3.12 was not found. Pass its path with: .\repair_venv.ps1 -PythonPath C:\Path\To\python.exe"
}

if (-not (Test-Path $PythonPath)) {
    throw "Python executable does not exist: $PythonPath"
}

& $PythonPath -m venv --upgrade "$ProjectRoot\venv"

if (-not $SkipInstall) {
    & "$ProjectRoot\venv\Scripts\python.exe" -m pip install -r "$ProjectRoot\requirements.txt"
}

Write-Host "venv repaired with $PythonPath"
