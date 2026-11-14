"""对话接口：SSE 流式返回 LangGraph 执行过程。

完整会话持久化设计：
  - 前端每次生成 UUID session_id → 本入口收到后 upsert chat_session
  - 每轮 user 输入 / assistant 输出各写一条 message（带 external_session_id 冗余列）
  - 每条 SSE 事件写 chat_event（token 事件存累计文本，其他存结构化 payload）
  - 多轮对话：每轮开始前 load_history_messages 拉最近 10 条，注入 GraphState.history_messages
  - 所有落库操作 best-effort（try-except 只 log warn），不阻断 SSE 主链路

SSE 协议说明（sse_starlette Event 对象）：
  Event(event="token", data="...")     → "event: token\ndata: ...\n\n"
  Event(event="intent", data=json_str) → "event: intent\ndata: {...}\n\n"
  前端 ChatView.vue 用 fetch + ReadableStream 解析：
    按 \n\n 切分事件 → 取 event: 行 → 取 data: 行 → 分情况 JSON.parse 或直接文本
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import AsyncGenerator, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse, ServerSentEvent

from app.db import chat_store
from app.graph.graph import graph

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["chat"])


# ---------------------------------------------------------------------------
# 请求 / 响应模型
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    question: str
    tenant_id: str
    session_id: Optional[str] = None
    trace_id: Optional[str] = None


# ---------------------------------------------------------------------------
# 内部工具
# ---------------------------------------------------------------------------

def _ensure_session_id(req_session_id: Optional[str]) -> str:
    sid = (req_session_id or "").strip()
    if not sid:
        sid = uuid.uuid4().hex
    return sid


def _schedule_save_event(*, external_id, tenant_id, message_round, event_name,
                          event_data=None, is_token=False, token_content=None, trace_id=None):
    """同步 chat_store.save_chat_event 放到后台线程池（best-effort，吞异常）。"""
    kwargs = dict(
        external_id=external_id, tenant_id=tenant_id, message_round=message_round,
        event_name=event_name, event_data=event_data, is_token=is_token,
        token_content=token_content, trace_id=trace_id,
    )
    def _run():
        try:
            chat_store.save_chat_event(**kwargs)
        except Exception as exc:
            logger.debug("chat_event 异步落库失败 %s: %s", event_name, exc)
    asyncio.get_running_loop().run_in_executor(None, _run)


def _event(event_name: str, data) -> ServerSentEvent:
    """构造 SSE 事件对象。data 为 dict 时自动 JSON 序列化，str 时直接用。"""
    if isinstance(data, (dict, list)):
        data_str = json.dumps(data, ensure_ascii=False)
    else:
        data_str = str(data)
    return ServerSentEvent(event=event_name, data=data_str)


# ---------------------------------------------------------------------------
# 主入口：流式对话
# ---------------------------------------------------------------------------

async def _stream_chat(req: ChatRequest) -> AsyncGenerator[ServerSentEvent, None]:
    """流式生成 SSE 事件 + 持久化每轮对话。"""
    trace_id = req.trace_id or uuid.uuid4().hex
    session_id = _ensure_session_id(req.session_id)
    tenant_id = req.tenant_id

    # --- 1) 会话 upsert + 历史加载 ---
    session_internal_id = chat_store.upsert_chat_session(session_id, tenant_id)
    history = chat_store.load_history_messages(session_id, tenant_id, limit=10)
    message_round = (len(history) // 2) + 1 if history else 1
    logger.info(
        "会话 session_id=%s tenant=%s round=%s history=%d trace=%s",
        session_id, tenant_id, message_round, len(history), trace_id,
    )

    # --- 2) user 输入先落库 ---
    chat_store.save_message(
        external_id=session_id, tenant_id=tenant_id, role="user",
        content=req.question, session_internal_id=session_internal_id,
    )

    # --- 3) 构造 initial_state ---
    initial_state = {
        "question": req.question,
        "tenant_id": tenant_id,
        "session_id": session_id,
        "trace_id": trace_id,
        "session_internal_id": session_internal_id or 0,
        "message_round": message_round,
        "history_messages": history,
    }

    # --- 4) start 事件 ---
    start_payload = {
        "question": req.question, "trace_id": trace_id,
        "session_id": session_id, "round": message_round,
        "history_count": len(history),
    }
    chat_store.save_chat_event(
        external_id=session_id, tenant_id=tenant_id, message_round=message_round,
        event_name="start", event_data=start_payload, trace_id=trace_id,
    )
    yield _event("start", start_payload)

    review_payload: dict | None = None
    model_payload: dict | None = None
    degraded = False
    fail_records: list[dict] = []
    final_answer = ""
    final_citations: list[dict] = []

    # --- 5) 跑 graph ---
    async for graph_event in graph.astream(initial_state, stream_mode="updates"):
        for node_name, update in graph_event.items():

            # --- 节点级结构化错误 ---
            node_err = update.get("error")
            if isinstance(node_err, dict) and node_err.get("fail_code"):
                degraded = True
                record = {
                    "node": node_err.get("fail_node", node_name),
                    "code": node_err["fail_code"],
                    "message": node_err.get("error_message", ""),
                }
                fail_records.append(record)
                _schedule_save_event(
                    external_id=session_id, tenant_id=tenant_id,
                    message_round=message_round, event_name="error",
                    event_data=record, trace_id=trace_id,
                )
                yield _event("error", record)

            # --- router ---
            if node_name == "router" and "intent" in update:
                ev = {"intent": update["intent"]}
                _schedule_save_event(
                    external_id=session_id, tenant_id=tenant_id,
                    message_round=message_round, event_name="intent",
                    event_data=ev, trace_id=trace_id,
                )
                yield _event("intent", ev)

            # --- retrieval ---
            elif node_name == "retrieval" and "chunks" in update:
                chunks = update.get("chunks", [])
                ev = {"count": len(chunks)}
                _schedule_save_event(
                    external_id=session_id, tenant_id=tenant_id,
                    message_round=message_round, event_name="retrieval",
                    event_data=ev, trace_id=trace_id,
                )
                yield _event("retrieval", {"count": len(chunks), "chunks": chunks[:3]})

            # --- answer ---
            elif node_name == "answer":
                if "answer" in update:
                    final_answer = update["answer"]
                    _schedule_save_event(
                        external_id=session_id, tenant_id=tenant_id,
                        message_round=message_round, event_name="token",
                        is_token=True, token_content=update["answer"],
                        trace_id=trace_id,
                    )
                    yield _event("token", update["answer"])
                if "citations" in update and update.get("citations"):
                    final_citations = update["citations"]
                    _schedule_save_event(
                        external_id=session_id, tenant_id=tenant_id,
                        message_round=message_round, event_name="citations",
                        event_data=update["citations"], trace_id=trace_id,
                    )
                    yield _event("citations", update["citations"])
                if update.get("model_used"):
                    model_payload = {"provider": update.get("model_used"),
                                     "model": update.get("model_name")}
                    _schedule_save_event(
                        external_id=session_id, tenant_id=tenant_id,
                        message_round=message_round, event_name="model",
                        event_data=model_payload, trace_id=trace_id,
                    )
                    yield _event("model", model_payload)

            # --- chat（自由对话） ---
            elif node_name == "chat":
                if "answer" in update:
                    final_answer = update["answer"]
                    _schedule_save_event(
                        external_id=session_id, tenant_id=tenant_id,
                        message_round=message_round, event_name="token",
                        is_token=True, token_content=update["answer"],
                        trace_id=trace_id,
                    )
                    yield _event("token", update["answer"])
                if update.get("model_used"):
                    model_payload = {"provider": update.get("model_used"),
                                     "model": update.get("model_name")}
                    _schedule_save_event(
                        external_id=session_id, tenant_id=tenant_id,
                        message_round=message_round, event_name="model",
                        event_data=model_payload, trace_id=trace_id,
                    )
                    yield _event("model", model_payload)

            # --- nl2sql ---
            elif node_name == "nl2sql":
                if update.get("sql"):
                    _schedule_save_event(
                        external_id=session_id, tenant_id=tenant_id,
                        message_round=message_round, event_name="sql",
                        event_data={"sql": update["sql"]}, trace_id=trace_id,
                    )
                    yield _event("sql", {"sql": update["sql"]})
                if "rows" in update:
                    result_ev = {
                        "columns": update.get("columns", []),
                        "row_count": update.get("row_count", 0),
                        "status": update.get("status", "success"),
                    }
                    _schedule_save_event(
                        external_id=session_id, tenant_id=tenant_id,
                        message_round=message_round, event_name="result",
                        event_data=result_ev, trace_id=trace_id,
                    )
                    yield _event("result", {**result_ev, "rows": update.get("rows", [])[:50]})
                if "answer" in update:
                    final_answer = update["answer"]
                    _schedule_save_event(
                        external_id=session_id, tenant_id=tenant_id,
                        message_round=message_round, event_name="token",
                        is_token=True, token_content=update["answer"],
                        trace_id=trace_id,
                    )
                    yield _event("token", update["answer"])
                if update.get("citations"):
                    final_citations = update["citations"]
                    _schedule_save_event(
                        external_id=session_id, tenant_id=tenant_id,
                        message_round=message_round, event_name="citations",
                        event_data=update["citations"], trace_id=trace_id,
                    )
                    yield _event("citations", update["citations"])
                if update.get("model_used"):
                    model_payload = {"provider": update.get("model_used"),
                                     "model": update.get("model_name")}
                    _schedule_save_event(
                        external_id=session_id, tenant_id=tenant_id,
                        message_round=message_round, event_name="model",
                        event_data=model_payload, trace_id=trace_id,
                    )
                    yield _event("model", model_payload)

            # --- report ---
            elif node_name == "report":
                if update.get("sql"):
                    _schedule_save_event(
                        external_id=session_id, tenant_id=tenant_id,
                        message_round=message_round, event_name="sql",
                        event_data={"sql": update["sql"]}, trace_id=trace_id,
                    )
                    yield _event("sql", {"sql": update["sql"]})
                if update.get("chart_option") is not None and "rows" in update:
                    report_ev = {
                        "report_id": update.get("report_id"),
                        "title": update.get("report_title", "数据报表"),
                        "chart_type": update.get("chart_type", "none"),
                        "columns": update.get("columns", []),
                        "row_count": update.get("row_count", 0),
                        "status": update.get("status", "success"),
                    }
                    _schedule_save_event(
                        external_id=session_id, tenant_id=tenant_id,
                        message_round=message_round, event_name="report",
                        event_data=report_ev, trace_id=trace_id,
                    )
                    full = {
                        **report_ev, "option": update.get("chart_option", {}),
                        "rows": update.get("rows", [])[:50],
                        "summary": update.get("answer", ""),
                    }
                    yield _event("report", full)
                if "answer" in update:
                    final_answer = update["answer"]
                    _schedule_save_event(
                        external_id=session_id, tenant_id=tenant_id,
                        message_round=message_round, event_name="token",
                        is_token=True, token_content=update["answer"],
                        trace_id=trace_id,
                    )
                    yield _event("token", update["answer"])
                if update.get("citations"):
                    final_citations = update["citations"]
                    _schedule_save_event(
                        external_id=session_id, tenant_id=tenant_id,
                        message_round=message_round, event_name="citations",
                        event_data=update["citations"], trace_id=trace_id,
                    )
                    yield _event("citations", update["citations"])
                if update.get("model_used"):
                    model_payload = {"provider": update.get("model_used"),
                                     "model": update.get("model_name")}
                    _schedule_save_event(
                        external_id=session_id, tenant_id=tenant_id,
                        message_round=message_round, event_name="model",
                        event_data=model_payload, trace_id=trace_id,
                    )
                    yield _event("model", model_payload)

            # --- review ---
            elif node_name == "review" and update.get("review"):
                review_payload = update["review"]
                if update.get("model_used") and not model_payload:
                    model_payload = {"provider": update.get("model_used"),
                                     "model": update.get("model_name")}
                final_answer = review_payload.get("answer", final_answer)
                final_review_ev = {
                    "passed": review_payload.get("passed"),
                    "level": review_payload.get("level"),
                    "issues": review_payload.get("issues", []),
                    "model": model_payload,
                }
                _schedule_save_event(
                    external_id=session_id, tenant_id=tenant_id,
                    message_round=message_round, event_name="review",
                    event_data=final_review_ev, trace_id=trace_id,
                )
                yield _event("review", {**final_review_ev, "answer": final_answer})

            # --- clarify ---
            elif node_name == "clarify" and "answer" in update:
                final_answer = update["answer"]
                _schedule_save_event(
                    external_id=session_id, tenant_id=tenant_id,
                    message_round=message_round, event_name="token",
                    is_token=True, token_content=update["answer"],
                    trace_id=trace_id,
                )
                yield _event("token", update["answer"])

    # --- 6) graph 完成 → assistant 落库 + done ---
    chat_store.save_message(
        external_id=session_id, tenant_id=tenant_id, role="assistant",
        content=final_answer, citations=final_citations or None,
        session_internal_id=session_internal_id,
    )
    chat_store.touch_session_activity(session_id, tenant_id)
    if message_round == 1:
        title = (req.question or "").strip()[:40] or "新会话"
        chat_store.update_session_title(session_id, tenant_id, title)

    status = "completed_with_degradation" if degraded else "completed"
    done_payload = {
        "status": status,
        "trace_id": trace_id,
        "session_id": session_id,
        "round": message_round,
        "model": model_payload,
        "review": {
            "passed": (review_payload or {}).get("passed"),
            "issues": (review_payload or {}).get("issues", []),
        },
        "degraded": degraded,
        "failures": fail_records,
    }
    _schedule_save_event(
        external_id=session_id, tenant_id=tenant_id,
        message_round=message_round, event_name="done",
        event_data=done_payload, trace_id=trace_id,
    )
    yield _event("done", done_payload)


@router.post("/chat/stream")
async def chat_stream(req: ChatRequest) -> EventSourceResponse:
    return EventSourceResponse(_stream_chat(req))


# ---------------------------------------------------------------------------
# 历史查询 API
# ---------------------------------------------------------------------------

@router.get("/chat/sessions")
async def list_sessions(
    tenant_id: str,
    keyword: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> JSONResponse:
    """历史会话列表：按关键词 / 时间范围过滤，last_active_at 倒序。"""
    sessions = chat_store.list_sessions(
        tenant_id, keyword=keyword, start=start, end=end, limit=limit, offset=offset
    )
    return JSONResponse(content={"sessions": sessions, "total": len(sessions)})


@router.get("/chat/sessions/{session_id}/messages")
async def get_session_messages(session_id: str, tenant_id: str) -> JSONResponse:
    """会话完整消息流（时间升序），用于页面恢复历史对话。"""
    messages = chat_store.get_session_messages(session_id, tenant_id, limit=200)
    return JSONResponse(content={"session_id": session_id, "messages": messages})


@router.get("/chat/sessions/{session_id}/timeline")
async def get_session_timeline(session_id: str, tenant_id: str) -> JSONResponse:
    """拉取该会话的完整 SSE 事件时间线，按 round 分组。"""
    try:
        import psycopg
        from app.config import settings
        with psycopg.connect(settings.postgres_dsn, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT message_round, event_name, event_data, is_token,
                           token_content, created_at, trace_id
                    FROM chat_event
                    WHERE external_session_id = %s AND tenant_id = %s
                    ORDER BY message_round ASC, created_at ASC
                    """,
                    (session_id, tenant_id),
                )
                rows = cur.fetchall()
    except Exception as exc:
        logger.warning("timeline 查询失败 session_id=%s: %s", session_id, exc)
        raise HTTPException(status_code=500, detail=str(exc))

    rounds: dict[int, list[dict]] = {}
    for r in rows:
        (mr, name, data, is_token, tok, created_at, trace_id) = r
        rounds.setdefault(mr, []).append({
            "event_name": name, "event_data": data,
            "is_token": bool(is_token), "token_content": tok,
            "trace_id": trace_id, "created_at": created_at.isoformat(),
        })
    return JSONResponse(content={
        "session_id": session_id,
        "rounds": [{"round": k, "events": v} for k, v in sorted(rounds.items())],
    })
