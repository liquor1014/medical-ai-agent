# 一键启动完整栈（Windows PowerShell）
# 用法：.\scripts\start.ps1            # 构建并启动
#       .\scripts\start.ps1 -NoBuild   # 跳过构建，仅启动
#       .\scripts\start.ps1 -FollowLogs # 启动后跟踪日志

param(
    [switch]$NoBuild,
    [switch]$FollowLogs,
    [int]$TimeoutSeconds = 300
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw '未找到 docker 命令，请先安装并启动 Docker Desktop'
}
try {
    & docker info | Out-Null
} catch {
    throw 'Docker 未运行，请先启动 Docker Desktop'
}

if (-not (Test-Path '.env')) {
    Copy-Item '.env.example' '.env'
    Write-Host '已根据 .env.example 创建 .env（可在其中填写模型 API Key）' -ForegroundColor Cyan
}

if ($NoBuild) {
    Write-Host '==> docker compose up -d' -ForegroundColor Cyan
    & docker compose up -d
} else {
    Write-Host '==> docker compose up -d --build（首次构建可能较慢）' -ForegroundColor Cyan
    & docker compose up -d --build
}
if ($LASTEXITCODE -ne 0) {
    throw 'docker compose 启动失败，请查看上方的错误输出'
}

function Wait-Health {
    param([string]$Name, [string]$Url)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
            if ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 400) {
                Write-Host "  [OK]   $Name" -ForegroundColor Green
                return $true
            }
        } catch {
            # 服务尚未就绪，继续等待
        }
        Start-Sleep -Seconds 3
    }
    Write-Host "  [WARN] $Name 未在 $TimeoutSeconds 秒内就绪：$Url" -ForegroundColor Yellow
    return $false
}

$webPort = if ($env:WEB_PORT) { $env:WEB_PORT } else { '5173' }

Write-Host ''
Write-Host '==> 等待服务就绪' -ForegroundColor Cyan
$okBackend = Wait-Health '后端控制面' 'http://localhost:8080/actuator/health'
$okAi = Wait-Health 'AI 服务' 'http://localhost:8000/health'
$okWeb = Wait-Health '前端页面' "http://localhost:$webPort/"

Write-Host ''
Write-Host '========================================' -ForegroundColor Cyan
Write-Host ' 医疗文件检索与报表统计 Agent 已启动' -ForegroundColor Cyan
Write-Host '========================================' -ForegroundColor Cyan
Write-Host "  前端      http://localhost:$webPort"
Write-Host '  后端      http://localhost:8080'
Write-Host '  AI 服务   http://localhost:8000/docs'
Write-Host '  MinIO     http://localhost:9001  (minioadmin / minioadmin123)'
Write-Host '  演示账号  admin / admin123 或 doctor / doctor123'
Write-Host '  停止服务  .\scripts\stop.ps1'
Write-Host '========================================' -ForegroundColor Cyan

if (-not ($okBackend -and $okAi -and $okWeb)) {
    Write-Host '部分服务未就绪，可执行 docker compose logs -f 排查' -ForegroundColor Yellow
}

if ($FollowLogs) {
    & docker compose logs -f
}
