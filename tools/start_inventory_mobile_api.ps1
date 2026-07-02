param(
    [string]$HostAddress = "0.0.0.0",
    [int]$Port = 8787
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

Write-Host "StockLam mobile inventory API" -ForegroundColor Cyan
Write-Host "Built-in mobile app key: enabled" -ForegroundColor Green
Write-Host "Listening: http://$HostAddress`:$Port"
Write-Host "Phone URL: http://<PC_IP>:$Port"
Write-Host "Local network IPv4 addresses:" -ForegroundColor Cyan
Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object { $_.IPAddress -notlike '127.*' -and $_.PrefixOrigin -ne 'WellKnown' } |
    Select-Object -ExpandProperty IPAddress |
    ForEach-Object { Write-Host "  http://$_`:$Port" }

& venv\Scripts\python.exe tools\inventory_mobile_api.py --host $HostAddress --port $Port
