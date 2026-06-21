param(
    [string]$HostName = "127.0.0.1",
    [int]$Port = 8000,
    [switch]$Reload
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $ProjectRoot

$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "未找到虚拟环境，请先执行 scripts\windows\setup.ps1"
}

$Arguments = @("-m", "uvicorn", "app.main:app", "--host", $HostName, "--port", "$Port")
if ($Reload) {
    $Arguments += "--reload"
}

Write-Host "后台启动中：http://$HostName`:$Port/"
& $Python @Arguments
