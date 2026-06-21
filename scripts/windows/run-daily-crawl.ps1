param(
    [int]$Limit = 0,
    [switch]$NoNotify
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $ProjectRoot

$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "未找到虚拟环境，请先执行 scripts\windows\setup.ps1"
}

$Arguments = @("-m", "app.cli", "run-daily-crawl")
if ($Limit -gt 0) {
    $Arguments += @("--limit", "$Limit")
}
if ($NoNotify) {
    $Arguments += "--no-notify"
}

& $Python @Arguments
