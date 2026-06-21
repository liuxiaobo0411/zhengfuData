param(
    [string]$PythonCommand = "py",
    [switch]$SkipImportSites
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $ProjectRoot

if (-not (Test-Path ".venv")) {
    & $PythonCommand -m venv .venv
}

$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "未找到虚拟环境 Python：$Python"
}

& $Python -m pip install --upgrade pip
& $Python -m pip install -e ".[dev]"

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "已创建 .env，请在正式使用前修改 ADMIN_PASSWORD、APP_SECRET_KEY 和 OPENCLAW_WEBHOOK_URL。"
}

& $Python -m alembic upgrade head

if (-not $SkipImportSites) {
    & $Python -m app.cli import-sites --file configs/sites.yaml
}

Write-Host "Windows 初始化完成。"
Write-Host "启动后台：scripts\windows\run-server.ps1"
Write-Host "运行每日抓取：scripts\windows\run-daily-crawl.ps1"
