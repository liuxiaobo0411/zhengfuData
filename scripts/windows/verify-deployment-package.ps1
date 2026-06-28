param(
    [Parameter(Mandatory = $true)]
    [string]$PackagePath,
    [string]$PythonCommand = "python",
    [string]$WorkRoot = ""
)

. "$PSScriptRoot\_bootstrap.ps1"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $ProjectRoot

$ResolvedPackage = (Resolve-Path $PackagePath).Path
if (-not $WorkRoot) {
    $WorkRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("zhengfudata-package-check-" + [System.Guid]::NewGuid().ToString("N"))
}

if (Test-Path $WorkRoot) {
    Remove-Item $WorkRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $WorkRoot | Out-Null

Write-Host "解压部署包：$ResolvedPackage"
Expand-Archive -Path $ResolvedPackage -DestinationPath $WorkRoot -Force

$ExtractedRoot = Join-Path $WorkRoot "zhengfudata"
if (-not (Test-Path $ExtractedRoot)) {
    throw "部署包中未找到 zhengfudata 根目录"
}

$RequiredFiles = @(
    "README.md",
    ".env.example",
    "pyproject.toml",
    "configs\sites.yaml",
    "scripts\windows\setup.ps1",
    "scripts\windows\doctor.ps1",
    "scripts\windows\run-local-acceptance.ps1",
    "DEPLOYMENT_PACKAGE_MANIFEST.txt"
)

foreach ($RelativePath in $RequiredFiles) {
    $Path = Join-Path $ExtractedRoot $RelativePath
    if (-not (Test-Path $Path)) {
        throw "部署包缺少必要文件：$RelativePath"
    }
}

$ForbiddenPaths = @(".env", "data", "storage", ".venv", ".git")
foreach ($RelativePath in $ForbiddenPaths) {
    $Path = Join-Path $ExtractedRoot $RelativePath
    if (Test-Path $Path) {
        throw "部署包不应包含本机状态目录或文件：$RelativePath"
    }
}

Push-Location $ExtractedRoot
try {
    & "scripts\windows\setup.ps1" -PythonCommand $PythonCommand
    & "scripts\windows\doctor.ps1"
    & "scripts\windows\run-local-acceptance.ps1" -SkipSourceValidation -SkipDailyCrawl -SkipV2
}
finally {
    Pop-Location
}

Write-Host "部署包解压安装验收完成：$ExtractedRoot"
