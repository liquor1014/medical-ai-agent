"""LangGraph 状态定义。"""
from __future__ import annotations

from typing import List, Optional, TypedDict


class GraphState(TypedDict, total=False):
    # --- 请求入口 ---
    question: str
    tenant_id: str
    session_id: str                    # 前端 UUID（external_id），全程透传
    trace_id: str

    # --- 会话持久化辅助 ---
    session_internal_id: int           # chat_session 自增主键（upsert 拿到的）
    message_round: int                 # 第几轮对话（从 1 开始）
    history_messages: List[dict]       # [{role, content}, ...] 最近 N 轮，给 answer 节点做多轮上下文

    # --- 路由 ---
    intent: str

    # --- RAG ---
    context: str
    chunks: List[dict]

    # --- 回答 ---
    answer: str
    citations: List[dict]

    # --- 模型路由 / 审查 ---
    model_used: str
    model_name: str
    review: dict

    # --- NL2SQL ---
    sql: str
    columns: List[str]
    rows: List[dict]
    row_count: int
    status: str

    # --- 报表 / 图表 ---
    report_id: Optional[int]
    report_title: str
    chart_type: str
    chart_option: dict

    # --- 错误（graph 节点降级时写入 dict；chat.py 识别并 yield error 事件）---
    error: Optional[dict]              # {fail_node, fail_code, error_message}
