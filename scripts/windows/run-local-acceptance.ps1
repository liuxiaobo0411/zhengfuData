param(
    [int]$SourceLimit = 2,
    [int]$DailyLimit = 2,
    [switch]$SkipSourceValidation,
    [switch]$SkipDailyCrawl,
    [switch]$SkipV2,
    [switch]$SkipV3
)

. "$PSScriptRoot\_bootstrap.ps1"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $ProjectRoot

$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "未找到虚拟环境，请先执行 scripts\windows\setup.ps1"
}

$Arguments = @(
    "-m",
    "app.cli",
    "local-acceptance-check",
    "--source-limit",
    "$SourceLimit",
    "--daily-limit",
    "$DailyLimit"
)
if ($SkipSourceValidation) {
    $Arguments += "--skip-source-validation"
}
if ($SkipDailyCrawl) {
    $Arguments += "--skip-daily-crawl"
}
if ($SkipV2) {
    $Arguments += "--skip-v2"
}
if ($SkipV3) {
    $Arguments += "--skip-v3"
}

& $Python @Arguments
if ($LASTEXITCODE -ne 0) {
    throw "Windows 本机验收流程执行失败，退出码：$LASTEXITCODE"
}

Write-Host ""
Write-Host "Windows 本机验收流程执行完成。"
