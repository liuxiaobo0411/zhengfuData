param(
    [string]$TaskName = "ZhengfuDataDailyCrawl",
    [string]$DailyTime = "09:00"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$ScriptPath = Join-Path $ProjectRoot "scripts\windows\run-daily-crawl.ps1"

if (-not (Test-Path $ScriptPath)) {
    throw "未找到每日抓取脚本：$ScriptPath"
}

$Action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptPath`""
$Trigger = New-ScheduledTaskTrigger -Daily -At $DailyTime
$Settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 6)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "建筑资质公开信息监测与归档系统每日抓取" `
    -Force

Write-Host "已注册 Windows 任务计划：$TaskName，每天 $DailyTime 执行。"
