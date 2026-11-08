"""对话接口：SSE 流式返回 LangGraph 执行过程。"""
from __future__ import annotations

import json
import logging
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.graph.graph import graph

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    question: str
    tenant_id: str
    session_id: str | None = None
    trace_id: str | None = None


async def _stream_chat(req: ChatRequest) -> AsyncGenerator[dict, None]:
    """流式生成 SSE 事件。"""
    trace_id = req.trace_id or uuid.uuid4().hex
    initial_state = {
        "question": req.question,
        "tenant_id": req.tenant_id,
        "trace_id": trace_id,
    }

    # 事件1：开始
    yield {
        "event": "start",
        "data": json.dumps({"question": req.question, "trace_id": trace_id},
                           ensure_ascii=False),
    }

    review_payload: dict | None = None
    model_payload: dict | None = None

    try:
        async for event in graph.astream(initial_state, stream_mode="updates"):
            # stream_mode="updates" 返回 {node_name: state_update}
            for node_name, update in event.items():
                # 按节点名过滤，避免后续节点回传完整 state 导致重复事件
                if node_name == "router" and "intent" in update:
                    yield {"event": "intent", "data": json.dumps({"intent": update["intent"]})}

                elif node_name == "retrieval" and "chunks" in update:
                    chunks = update.get("chunks", [])
                    yield {
                        "event": "retrieval",
                        "data": json.dumps({"count": len(chunks), "chunks": chunks[:3]}),
                    }

                elif node_name == "nl2sql":
                    if update.get("sql"):
                        yield {
                            "event": "sql",
                            "data": json.dumps({"sql": update["sql"]}, ensure_ascii=False),
                        }
                    if "rows" in update:
                        yield {
                            "event": "result",
                            "data": json.dumps(
                                {
                                    "columns": update.get("columns", []),
                                    "rows": update.get("rows", [])[:50],
                                    "row_count": update.get("row_count", 0),
                                    "status": update.get("status", "success"),
                                },
                                ensure_ascii=False,
                            ),
                        }
                    if "answer" in update:
                        yield {"event": "token", "data": update["answer"]}
                    if update.get("citations"):
                        yield {
                            "event": "citations",
                            "data": json.dumps(update["citations"], ensure_ascii=False),
                        }
                    if update.get("model_used"):
                        model_payload = {
                            "provider": update.get("model_used"),
                            "model": update.get("model_name"),
                        }
                        yield {"event": "model", "data": json.dumps(model_payload,
                                                                   ensure_ascii=False)}

                elif node_name == "report":
                    if update.get("sql"):
                        yield {
                            "event": "sql",
                            "data": json.dumps({"sql": update["sql"]}, ensure_ascii=False),
                        }
                    if update.get("chart_option") is not None and "rows" in update:
                        yield {
                            "event": "report",
                            "data": json.dumps(
                                {
                                    "report_id": update.get("report_id"),
                                    "title": update.get("report_title", "数据报表"),
                                    "chart_type": update.get("chart_type", "none"),
                                    "option": update.get("chart_option", {}),
                                    "columns": update.get("columns", []),
                                    "rows": update.get("rows", [])[:50],
                                    "row_count": update.get("row_count", 0),
                                    "status": update.get("status", "success"),
                                    "summary": update.get("answer", ""),
                                },
                                ensure_ascii=False,
                            ),
                        }
                    if "answer" in update:
                        yield {"event": "token", "data": update["answer"]}
                    if update.get("citations"):
                        yield {
                            "event": "citations",
                            "data": json.dumps(update["citations"], ensure_ascii=False),
                        }
                    if update.get("model_used"):
                        model_payload = {
                            "provider": update.get("model_used"),
                            "model": update.get("model_name"),
                        }
                        yield {"event": "model", "data": json.dumps(model_payload,
                                                                   ensure_ascii=False)}

                elif node_name == "answer":
                    if "answer" in update:
                        yield {"event": "token", "data": update["answer"]}
                    if "citations" in update and update.get("citations"):
                        yield {"event": "citations",
                               "data": json.dumps(update["citations"], ensure_ascii=False)}
                    if update.get("model_used"):
                        model_payload = {
                            "provider": update.get("model_used"),
                            "model": update.get("model_name"),
                        }
                        yield {"event": "model", "data": json.dumps(model_payload,
                                                                   ensure_ascii=False)}

                elif node_name == "review" and update.get("review"):
                    review_payload = update["review"]
                    if update.get("model_used") and not model_payload:
                        model_payload = {
                            "provider": update.get("model_used"),
                            "model": update.get("model_name"),
                        }
                    yield {
                        "event": "review",
                        "data": json.dumps(
                            {
                                "passed": review_payload.get("passed"),
                                "level": review_payload.get("level"),
                                "issues": review_payload.get("issues", []),
                                "answer": review_payload.get("answer", ""),
                                "model": model_payload,
                            },
                            ensure_ascii=False,
                        ),
                    }

        yield {
            "event": "done",
            "data": json.dumps(
                {
                    "status": "completed",
                    "trace_id": trace_id,
                    "model": model_payload,
                    "review": {
                        "passed": (review_payload or {}).get("passed"),
                        "issues": (review_payload or {}).get("issues", []),
                    },
                },
                ensure_ascii=False,
            ),
        }
    except Exception as e:
        logger.exception("对话执行失败")
        yield {"event": "error", "data": json.dumps({"message": str(e)}, ensure_ascii=False)}


@router.post("/chat/stream")
async def chat_stream(req: ChatRequest) -> EventSourceResponse:
    return EventSourceResponse(_stream_chat(req))
