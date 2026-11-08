"""LangGraph 状态定义。"""
from __future__ import annotations

from typing import List, Optional, TypedDict


class GraphState(TypedDict, total=False):
    question: str
    tenant_id: str
    intent: str
    context: str
    chunks: List[dict]
    answer: str
    citations: List[dict]
    error: Optional[str]
    # 模型路由 / 审查
    trace_id: str
    model_used: str
    model_name: str
    review: dict
    # NL2SQL 结果
    sql: str
    columns: List[str]
    rows: List[dict]
    row_count: int
    status: str
    # 报表 / 图表
    report_id: Optional[int]
    report_title: str
    chart_type: str
    chart_option: dict
