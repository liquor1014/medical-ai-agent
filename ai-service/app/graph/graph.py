"""LangGraph 构建：路由 → 检索/问答 → Reviewer 输出。"""
from __future__ import annotations

import logging
from typing import AsyncGenerator

from langgraph.graph import END, START, StateGraph

from app.agents.report.report_agent import generate_report
from app.agents.nl2sql.nl2sql_agent import run_nl2sql
from app.agents.retrieval.retrieval_agent import format_context, retrieve
from app.agents.reviewer.reviewer_agent import review_answer
from app.agents.router.router_agent import Intent, classify
from app.graph.state import GraphState
from app.llm.providers import llm

logger = logging.getLogger(__name__)


def router_node(state: GraphState) -> GraphState:
    """意图路由节点。"""
    question = state["question"]
    intent = classify(question)
    logger.info("路由意图: %s", intent.value)
    return {**state, "intent": intent.value}


def route_after_router(state: GraphState) -> str:
    """根据意图选择下一个节点。"""
    intent = state.get("intent")
    if intent == Intent.RETRIEVAL.value:
        return "retrieval"
    if intent == Intent.NL2SQL.value:
        return "nl2sql"
    if intent == Intent.REPORT.value:
        return "report"
    return END


def retrieval_node(state: GraphState) -> GraphState:
    """RAG 检索节点。"""
    question = state["question"]
    tenant_id = state["tenant_id"]
    chunks = retrieve(question, tenant_id)
    context = format_context(chunks)
    return {**state, "chunks": chunks, "context": context}


async def answer_node(state: GraphState) -> AsyncGenerator[GraphState, None]:
    """生成回答节点（流式），结束后带回实际使用的模型。"""
    question = state["question"]
    context = state.get("context", "")
    chunks = state.get("chunks", [])
    trace_id = state.get("trace_id") or ""
    tenant_id = state.get("tenant_id", "")

    messages = [
        {"role": "system", "content": "你是医疗物资管理智能助手，基于文档内容回答问题，必须引用来源。"},
        {"role": "user", "content": question},
    ]

    full_answer = ""
    async for token in llm.chat_stream(
        messages, context, task="chat", tenant_id=tenant_id, trace_id=trace_id
    ):
        full_answer += token
        yield {**state, "answer": full_answer, "citations": chunks}

    trace = llm.get_trace(trace_id) or {}
    yield {
        **state,
        "answer": full_answer,
        "citations": chunks,
        "model_used": trace.get("provider", "mock"),
        "model_name": trace.get("model", "mock"),
    }


async def nl2sql_node(state: GraphState) -> GraphState:
    """NL2SQL 节点：生成并执行 SQL，返回结构化结果。"""
    question = state["question"]
    tenant_id = state["tenant_id"]
    result = await run_nl2sql(
        question, tenant_id, trace_id=state.get("trace_id", "")
    )
    trace = llm.get_trace(state.get("trace_id", "")) or {}
    return {
        **state,
        "sql": result["sql"],
        "columns": result["columns"],
        "rows": result["rows"],
        "row_count": len(result["rows"]),
        "status": result["status"],
        "answer": result["answer"],
        "citations": result.get("citations", []),
        "model_used": trace.get("provider") or "mock",
        "model_name": trace.get("model") or "mock",
    }


async def report_node(state: GraphState) -> GraphState:
    """报表节点：查询数据 + 构建图表配置。"""
    question = state["question"]
    tenant_id = state["tenant_id"]
    result = await generate_report(
        question, tenant_id, trace_id=state.get("trace_id", "")
    )
    trace = llm.get_trace(state.get("trace_id", "")) or {}
    return {
        **state,
        "sql": result["sql"],
        "columns": result["columns"],
        "rows": result["rows"],
        "row_count": len(result["rows"]),
        "status": result["status"],
        "report_id": result.get("report_id"),
        "report_title": result["report_title"],
        "chart_type": result["chart_type"],
        "chart_option": result["chart_option"],
        "answer": result["summary"],
        "model_used": trace.get("provider") or "mock",
        "model_name": trace.get("model") or "mock",
        "citations": [{"type": "report", "report_id": result.get("report_id"),
                       "title": result["report_title"], "row_count": len(result["rows"])}],
    }


def review_node(state: GraphState) -> GraphState:
    """Reviewer 节点：质量检查 + 免责声明。"""
    review = review_answer(state)
    return {**state, "answer": review["answer"], "review": review}


def build_graph():
    """构建 LangGraph。"""
    builder = StateGraph(GraphState)

    builder.add_node("router", router_node)
    builder.add_node("retrieval", retrieval_node)
    builder.add_node("answer", answer_node)
    builder.add_node("nl2sql", nl2sql_node)
    builder.add_node("report", report_node)
    builder.add_node("review", review_node)

    builder.add_edge(START, "router")
    builder.add_conditional_edges("router", route_after_router, {
        "retrieval": "retrieval",
        "nl2sql": "nl2sql",
        "report": "report",
    })
    builder.add_edge("retrieval", "answer")
    builder.add_edge("answer", "review")
    builder.add_edge("nl2sql", "review")
    builder.add_edge("report", "review")
    builder.add_edge("review", END)

    return builder.compile()


graph = build_graph()
