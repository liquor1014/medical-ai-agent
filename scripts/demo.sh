#!/usr/bin/env bash
# 本地环境连通性检查（需先启动 infra 与各服务）
set -euo pipefail

echo "== Java 控制面 =="
curl -fsS http://localhost:8080/actuator/health || echo "backend 未启动"

echo "== AI 服务 =="
curl -fsS http://localhost:8000/health || echo "ai-service 未启动"

echo "== PostgreSQL =="
pg_isready -h localhost -p 5432 || true

echo "== Qdrant =="
curl -fsS http://localhost:6333/healthz || true

echo "== MinIO =="
curl -fsS http://localhost:9000/minio/health/live || true

echo "== Redis =="
redis-cli -h localhost ping || true
