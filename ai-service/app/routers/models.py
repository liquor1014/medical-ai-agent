"""模型配置与可观测接口（Day 7）。

- GET  /api/models            当前提供者、路由、超时配置
- GET  /api/models/health     配置状态 + 近 24h 调用统计
- GET  /api/models/logs       最近调用日志（model_call_log）
- POST /api/models/switch     运行时切换某任务的路由（内存级）
- POST /api/models/test       走完整路由/降级链路做一次试调用
"""
from __future__ import annotations

import logging
from datetime import datetime

import psycopg
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import settings
from app.llm.providers import llm

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/models", tags=["models"])


class SwitchRequest(BaseModel):
    task: str = Field(default="chat", description="chat / nl2sql / report")
    providers: list[str] = Field(default_factory=list, description="按顺序尝试的提供者")
    reset: bool = Field(default=False, description="恢复环境变量中的默认路由")


class TestRequest(BaseModel):
    question: str = "用一句话说明当前使用的是哪个模型"
    task: str = "chat"
    tenant_id: str = "hospital-demo"


@router.get("")
def list_models() -> dict:
    return llm.describe()


@router.get("/health")
def model_health() -> dict:
    stats: list[dict] = []
    try:
        with psycopg.connect(settings.postgres_dsn, connect_timeout=2) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT provider, status, COUNT(*) AS calls,
                           COALESCE(AVG(latency_ms), 0)::int AS avg_latency_ms,
                           COALESCE(SUM(tokens), 0)::int AS tokens,
                           COALESCE(SUM(cost), 0)::float AS cost
                    FROM model_call_log
                    WHERE created_at > now() - interval '24 hours'
                    GROUP BY provider, status
                    ORDER BY provider, status
                    """
                )
                stats = [
                    {
                        "provider": r[0],
                        "status": r[1],
                        "calls": r[2],
                        "avg_latency_ms": r[3],
                        "tokens": r[4],
                        "cost": round(r[5], 6),
                    }
                    for r in cur.fetchall()
                ]
    except Exception as exc:
        logger.warning("读取模型调用统计失败（使用内存日志）: %s", exc)

    return {
        **llm.describe(),
        "stats_24h": stats,
        "recent": llm.recent_logs(5),
    }


@router.get("/logs")
def model_logs(limit: int = 20) -> dict:
    limit = max(1, min(limit, 200))
    try:
        with psycopg.connect(settings.postgres_dsn, connect_timeout=2) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT provider, model, task_type, status, latency_ms,
                           first_token_ms, tokens, cost, error, trace_id, created_at,
                           tenant_id, fallback_from
                    FROM model_call_log
                    ORDER BY id DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                rows = cur.fetchall()
        logs = [
            {
                "provider": r[0],
                "model": r[1],
                "task_type": r[2],
                "status": r[3],
                "latency_ms": r[4],
                "first_token_ms": r[5],
                "tokens": r[6],
                "cost": float(r[7] or 0),
                "error": r[8],
                "trace_id": r[9],
                "created_at": r[10].isoformat() if isinstance(r[10], datetime) else str(r[10]),
                "tenant_id": r[11],
                "fallback_from": r[12],
            }
            for r in rows
        ]
        return {"source": "postgres", "count": len(logs), "logs": logs}
    except Exception as exc:
        logger.warning("读取 model_call_log 失败，返回内存日志: %s", exc)
        return {"source": "memory", "count": len(llm.recent_logs(limit)),
                "logs": llm.recent_logs(limit)}


@router.post("/switch")
def switch_model(req: SwitchRequest) -> dict:
    try:
        if req.reset:
            routes = llm.reset_routes()
        else:
            llm.set_route(req.task, req.providers)
            routes = llm.describe()["routes"]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "routes": routes}


@router.post("/test")
async def test_model(req: TestRequest) -> dict:
    messages = [
        {"role": "system", "content": "你是医疗物资管理助手，请简短回答。"},
        {"role": "user", "content": req.question},
    ]
    result = await llm.chat_result(
        messages, task=req.task, tenant_id=req.tenant_id
    )
    return result.as_dict()
