#Requires -Version 5.0
<#
.SYNOPSIS
    AI Interviewer 一键部署打包脚本
.DESCRIPTION
    自动构建前端 → 准备部署包 → 生成 tar.gz 压缩包
    对应部署手册 3.1 ~ 3.3 步骤
.USAGE
    右键「使用 PowerShell 运行」或在 PowerShell 中执行:
    .\build-deploy.ps1
#>

[CmdletBinding()]
param(
    [string]$OutputDir = "deploy-package",
    [string]$PackageName = "ai-interviewer-deploy"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

Set-Location $ProjectRoot

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  AI Interviewer 部署打包脚本" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ---------- Step 1: 构建前端 ----------
Write-Host "[1/3] 构建前端 ..." -ForegroundColor Yellow

if (-not (Test-Path "node_modules")) {
    Write-Host "    检测到 node_modules 不存在，执行 npm install ..." -ForegroundColor DarkGray
    npm install
    if ($LASTEXITCODE -ne 0) {
        Write-Host "    npm install 失败！" -ForegroundColor Red
        exit 1
    }
}

npm run build
if ($LASTEXITCODE -ne 0) {
    Write-Host "    前端构建失败！" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path "dist")) {
    Write-Host "    dist/ 目录不存在，构建可能未成功" -ForegroundColor Red
    exit 1
}

$distSize = "{0:N2}" -f ((Get-ChildItem -Recurse dist | Measure-Object Length -Sum).Sum / 1MB)
Write-Host "    前端构建完成 (dist: $distSize MB)" -ForegroundColor Green

# ---------- Step 2: 准备部署包 ----------
Write-Host "[2/3] 准备部署包 ..." -ForegroundColor Yellow

if (Test-Path $OutputDir) {
    Remove-Item -Recurse -Force $OutputDir
}
New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null

$items = @(
    @{ Src = "dist";               Dst = "$OutputDir/dist" },
    @{ Src = "server";             Dst = "$OutputDir/server" },
    @{ Src = "Dockerfile";         Dst = "$OutputDir/Dockerfile" },
    @{ Src = "docker-compose.prod.yml"; Dst = "$OutputDir/docker-compose.prod.yml" },
    @{ Src = "deploy";             Dst = "$OutputDir/deploy" }
)

foreach ($item in $items) {
    if (-not (Test-Path $item.Src)) {
        Write-Host "    跳过不存在的文件: $($item.Src)" -ForegroundColor DarkYellow
        continue
    }
    if ((Get-Item $item.Src).PSIsContainer) {
        Copy-Item -Recurse $item.Src $item.Dst
    } else {
        Copy-Item $item.Src $item.Dst
    }
    Write-Host "    已复制: $($item.Src)" -ForegroundColor DarkGray
}

# 排除不需要的内容
$excludePatterns = @("__pycache__", "*.pyc", "*.pyo", ".env", ".git")
Get-ChildItem -Recurse $OutputDir | Where-Object {
    $name = $_.Name
    $excludePatterns -contains $name
} | ForEach-Object {
    Remove-Item -Recurse -Force $_.FullName -ErrorAction SilentlyContinue
}

# ---------- Step 3: 打包压缩 ----------
Write-Host "[3/3] 打包压缩 ..." -ForegroundColor Yellow

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$archiveName = "$PackageName-$timestamp"
$archivePath = Join-Path $ProjectRoot "$archiveName.tar.gz"

# 删除旧的压缩包
$oldPkg = Join-Path $ProjectRoot "$PackageName.tar.gz"
if (Test-Path $oldPkg) { Remove-Item $oldPkg }

# 在 deploy-package 目录内打包（保持相对路径结构）
Push-Location $OutputDir
tar -czf $archivePath .
Pop-Location

if (-not (Test-Path $archivePath)) {
    Write-Host "    压缩失败！" -ForegroundColor Red
    exit 1
}

$pkgSize = "{0:N2}" -f ((Get-Item $archivePath).Length / 1MB)

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  打包完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  压缩包: $archiveName.tar.gz" -ForegroundColor White
Write-Host "  大小:   $pkgSize MB" -ForegroundColor White
Write-Host "  路径:   $archivePath" -ForegroundColor White
Write-Host ""
Write-Host "  服务器部署步骤:" -ForegroundColor Cyan
Write-Host "    1. 上传 $archiveName.tar.gz 到服务器"
Write-Host "    2. tar -xzf $archiveName.tar.gz"
Write-Host "    3. docker compose -f docker-compose.prod.yml build --no-cache backend"
Write-Host "    4. docker compose -f docker-compose.prod.yml up -d"
Write-Host ""
