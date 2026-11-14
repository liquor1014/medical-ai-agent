"""模型配置与可观测接口（Day 7）。

- GET   /api/models                       当前提供者、路由、超时配置
- GET   /api/models/health                配置状态 + 近 24h 调用统计
- GET   /api/models/logs                  最近调用日志（model_call_log）
- POST  /api/models/switch                运行时切换某任务的路由（内存级）
- POST  /api/models/test                  走完整路由/降级链路做一次试调用
- POST  /api/models/providers             新增模型提供者并持久化
- PUT   /api/models/providers/{name}      编辑已有提供者配置并持久化
- PATCH /api/models/providers/{name}/enabled  启用/停用提供者并持久化
"""
from __future__ import annotations

import logging
import re
from datetime import datetime

import psycopg
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import settings
from app.db import model_provider_store
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


class ProviderCreateRequest(BaseModel):
    name: str = Field(..., description="提供者标识，小写字母/数字/下划线/中划线")
    model: str = Field(..., description="模型名称")
    base_url: str = Field(..., description="OpenAI 兼容接口地址")
    api_key: str = Field(default="", description="API Key；ollama 可留空")
    enabled: bool = Field(default=True, description="是否启用")


class ProviderUpdateRequest(BaseModel):
    model: str = Field(..., description="模型名称")
    base_url: str = Field(..., description="OpenAI 兼容接口地址")
    api_key: str = Field(default="", description="留空表示保持原 Key 不变")
    enabled: bool = Field(default=True, description="是否启用")


class ProviderToggleRequest(BaseModel):
    enabled: bool = Field(..., description="true 启用 / false 停用")


_NAME_RE = re.compile(r"^[a-z][a-z0-9_-]{1,31}$")
_RESERVED_NAMES = {"mock"}


def _normalize_name(name: str) -> str:
    value = (name or "").strip().lower()
    if not _NAME_RE.match(value):
        raise HTTPException(
            status_code=400,
            detail="提供者名称需为 2-32 位小写字母、数字、下划线或中划线，且以字母开头",
        )
    if value in _RESERVED_NAMES:
        raise HTTPException(status_code=400, detail="名称 mock 为系统保留，请更换")
    return value


def _normalize_endpoint(model: str, base_url: str) -> tuple[str, str]:
    model_value = (model or "").strip()
    url_value = (base_url or "").strip().rstrip("/")
    if not model_value:
        raise HTTPException(status_code=400, detail="模型名称不能为空")
    if not re.match(r"^https?://", url_value):
        raise HTTPException(status_code=400, detail="Base URL 需以 http:// 或 https:// 开头")
    return model_value, url_value


def _persist(name: str, model: str, base_url: str, api_key: str,
             enabled: bool, source: str) -> None:
    """配置变更实时落库；失败直接报错，避免页面显示成功但重启后丢失。"""
    try:
        model_provider_store.upsert_config(
            name=name,
            model=model,
            base_url=base_url,
            api_key=api_key,
            enabled=enabled,
            source=source,
        )
    except Exception as exc:
        logger.exception("模型提供者配置持久化失败: name=%s", name)
        raise HTTPException(
            status_code=503, detail="模型配置持久化失败，请检查数据库连接后重试"
        ) from exc


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


@router.post("/providers")
def create_provider(req: ProviderCreateRequest) -> dict:
    name = _normalize_name(req.name)
    if name in llm.provider_names:
        raise HTTPException(status_code=409, detail=f"提供者 {name} 已存在，请直接编辑")
    model, base_url = _normalize_endpoint(req.model, req.base_url)
    api_key = (req.api_key or "").strip()
    if not api_key and name != "ollama":
        raise HTTPException(status_code=400, detail="新增提供者需填写 API Key")

    _persist(name, model, base_url, api_key, req.enabled, "custom")
    provider = llm.upsert_provider(
        name=name, model=model, base_url=base_url,
        api_key=api_key, enabled=req.enabled, source="custom",
    )
    return {"ok": True, "provider": provider, "providers": llm.describe()["providers"]}


@router.put("/providers/{name}")
def update_provider(name: str, req: ProviderUpdateRequest) -> dict:
    key = _normalize_name(name)
    spec = llm.get_provider_spec(key)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"提供者 {key} 不存在")

    model, base_url = _normalize_endpoint(req.model, req.base_url)
    # 留空表示保持原 Key 不变，页面不会回显明文
    api_key = (req.api_key or "").strip() or spec.api_key

    _persist(key, model, base_url, api_key, req.enabled, spec.source)
    provider = llm.upsert_provider(
        name=key, model=model, base_url=base_url,
        api_key=api_key, enabled=req.enabled, source=spec.source,
    )
    return {"ok": True, "provider": provider, "providers": llm.describe()["providers"]}


@router.patch("/providers/{name}/enabled")
def toggle_provider(name: str, req: ProviderToggleRequest) -> dict:
    key = _normalize_name(name)
    spec = llm.get_provider_spec(key)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"提供者 {key} 不存在")

    _persist(key, spec.model, spec.base_url, spec.api_key, req.enabled, spec.source)
    provider = llm.set_provider_enabled(key, req.enabled)
    return {"ok": True, "provider": provider, "providers": llm.describe()["providers"]}
