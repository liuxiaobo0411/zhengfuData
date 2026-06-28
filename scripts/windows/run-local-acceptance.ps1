param(
    [int]$SourceLimit = 2,
    [int]$DailyLimit = 2,
    [switch]$SkipDailyCrawl,
    [switch]$SkipV2
)

. "$PSScriptRoot\_bootstrap.ps1"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $ProjectRoot

$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "未找到虚拟环境，请先执行 scripts\windows\setup.ps1"
}

function Invoke-AcceptanceStep {
    param(
        [string]$Name,
        [string[]]$Arguments
    )

    Write-Host ""
    Write-Host "==> $Name"
    & $Python @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Name 执行失败，退出码：$LASTEXITCODE"
    }
}

Invoke-AcceptanceStep "部署自检" @("-m", "app.cli", "doctor")
Invoke-AcceptanceStep "来源抽样验证" @("-m", "app.cli", "validate-sources", "--limit", "$SourceLimit")

if (-not $SkipDailyCrawl) {
    Invoke-AcceptanceStep "每日抓取抽样（不发送通知）" @(
        "-m",
        "app.cli",
        "run-daily-crawl",
        "--limit",
        "$DailyLimit",
        "--no-notify"
    )
}
else {
    Write-Host ""
    Write-Host "==> 每日抓取抽样已跳过"
}

if (-not $SkipV2) {
    Invoke-AcceptanceStep "V2 知识库验收" @("-m", "app.cli", "v2-acceptance-check")
}
else {
    Write-Host ""
    Write-Host "==> V2 知识库验收已跳过"
}

Invoke-AcceptanceStep "导出验收报告" @("-m", "app.cli", "export-acceptance-report")

Write-Host ""
Write-Host "Windows 本机验收流程执行完成。"
