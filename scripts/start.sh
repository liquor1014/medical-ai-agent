#!/usr/bin/env bash
# 一键启动完整栈（macOS / Linux）
# 用法：bash scripts/start.sh [--no-build]
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

command -v docker >/dev/null 2>&1 || { echo "未找到 docker，请先安装 Docker"; exit 1; }
docker info >/dev/null 2>&1 || { echo "Docker 未运行，请先启动 Docker"; exit 1; }

if [ ! -f .env ]; then
  cp .env.example .env
  echo "已根据 .env.example 创建 .env（可在其中填写模型 API Key）"
fi

if [ "${1:-}" = "--no-build" ]; then
  echo "==> docker compose up -d"
  docker compose up -d
else
  echo "==> docker compose up -d --build（首次构建可能较慢）"
  docker compose up -d --build
fi

WEB_PORT_VALUE="${WEB_PORT:-5173}"

wait_health() {
  local name="$1" url="$2" deadline=$(( $(date +%s) + 300 ))
  while [ "$(date +%s)" -lt "$deadline" ]; do
    if curl -fsS --max-time 3 "$url" >/dev/null 2>&1; then
      echo "  [OK]   $name"
      return 0
    fi
    sleep 3
  done
  echo "  [WARN] $name 未在 300 秒内就绪：$url"
  return 1
}

echo
echo "==> 等待服务就绪"
wait_health "后端控制面" "http://localhost:8080/actuator/health" || true
wait_health "AI 服务" "http://localhost:8000/health" || true
wait_health "前端页面" "http://localhost:${WEB_PORT_VALUE}/" || true

cat <<EOF

========================================
 医疗文件检索与报表统计 Agent 已启动
========================================
  前端      http://localhost:${WEB_PORT_VALUE}
  后端      http://localhost:8080
  AI 服务   http://localhost:8000/docs
  MinIO     http://localhost:9001  (minioadmin / minioadmin123)
  演示账号  admin / admin123 或 doctor / doctor123
  停止服务  bash scripts/stop.sh
========================================
EOF
