. "$PSScriptRoot\_bootstrap.ps1"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $ProjectRoot

$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "未找到虚拟环境，请先执行 scripts\windows\setup.ps1"
}

& $Python -m app.cli v3-acceptance-check
