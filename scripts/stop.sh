#!/usr/bin/env bash
# 停止完整栈（macOS / Linux）
# 用法：bash scripts/stop.sh [--remove-volumes]
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ "${1:-}" = "--remove-volumes" ]; then
  echo "==> docker compose down -v（将删除数据库、MinIO、Qdrant 数据）"
  docker compose down -v
else
  echo "==> docker compose down"
  docker compose down
fi
