# 停止完整栈（Windows PowerShell）
# 用法：.\scripts\stop.ps1                  # 停止并移除容器
#       .\scripts\stop.ps1 -RemoveVolumes  # 连同数据库/存储数据一起清除

param(
    [switch]$RemoveVolumes
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if ($RemoveVolumes) {
    Write-Host '==> docker compose down -v（将删除数据库、MinIO、Qdrant 数据）' -ForegroundColor Yellow
    & docker compose down -v
} else {
    Write-Host '==> docker compose down' -ForegroundColor Cyan
    & docker compose down
}
