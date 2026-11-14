"""LangGraph 构建：路由 → 检索/问答 → Reviewer 输出。

每个节点独立捕获异常，降级为结构化 state 返回（带 fail_code / degraded 标记），
不再把 Python 异常冒泡给 LangGraph 导致整个 graph 崩溃。
"""
from __future__ import annotations

import logging
import traceback
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


# ---------------------------------------------------------------------------
# 异常 → 结构化 state 的辅助函数
# ---------------------------------------------------------------------------

def _log_node_error(node_name: str, state: GraphState, exc: BaseException) -> None:
    """统一记录节点异常，保留 trace_id / tenant_id 等上下文。"""
    trace_id = state.get("trace_id", "")
    tenant_id = state.get("tenant_id", "")
    question = (state.get("question") or "")[:80]
    logger.error(
        "节点异常 node=%s trace_id=%s tenant=%s question=%r error=%s",
        node_name, trace_id, tenant_id, question, exc,
    )
    logger.debug("节点异常 traceback:\n%s", traceback.format_exc())


def _fail_state(state: GraphState, node_name: str, fail_code: str,
                message: str, *, extra: dict | None = None) -> GraphState:
    """构造一个携带失败标记的 state 片段，供 chat.py 识别并 yield error 事件。"""
    payload = {
        "fail_node": node_name,
        "fail_code": fail_code,
        "error_message": message,
    }
    if extra:
        payload.update(extra)
    return {**state, "error": payload}  # type: ignore[typeddict-item]


# ---------------------------------------------------------------------------
# 节点定义
# ---------------------------------------------------------------------------

def router_node(state: GraphState) -> GraphState:
    """意图路由节点。"""
    try:
        question = state["question"]
        intent = classify(question)
        logger.info("路由意图: %s", intent.value)
        return {**state, "intent": intent.value}
    except Exception as exc:
        _log_node_error("router", state, exc)
        # 路由本身极难失败（只有规则 + 纯字符串操作），真失败走默认 RETRIEVAL 兜底
        return {
            **state,
            "intent": Intent.RETRIEVAL.value,
            **_fail_state(state, "router", "ROUTER_FAIL", str(exc)),
        }


def route_after_router(state: GraphState) -> str:
    """根据意图选择下一个节点。"""
    intent = state.get("intent")
    if intent == Intent.RETRIEVAL.value:
        return "retrieval"
    if intent == Intent.NL2SQL.value:
        return "nl2sql"
    if intent == Intent.REPORT.value:
        return "report"
    if intent == Intent.CHAT.value:
        return "chat"
    if intent == Intent.CLARIFY.value:
        return "clarify"
    logger.warning("未知意图 %s，走 chat 兜底", intent)
    return "chat"


def clarify_node(state: GraphState) -> GraphState:
    """意图不明确时给出反问提示（确定性规则，不调 LLM）。"""
    try:
        question = state.get("question", "").strip()
        if not question:
            answer = "请输入您的问题，例如「高值耗材验收流程」或「本月采购金额统计」。"
        else:
            answer = (
                f"「{question}」既可以理解为查制度文档，也可以理解为查统计数据。\n"
                "为了准确回答，请补充一下您想要哪种：\n"
                "• 查文档：例如「XX 制度里关于验收流程的规定」\n"
                "• 查数据：例如「本月各科室验收数量统计」\n"
                "• 生成报表：例如「供应商履约率报表」"
            )
        logger.info("意图澄清: question=%s", question)
        return {
            **state,
            "answer": answer,
            "intent": Intent.CLARIFY.value,
        }
    except Exception as exc:
        _log_node_error("clarify", state, exc)
        return {
            **state,
            "answer": "抱歉，当前服务暂不可用，请稍后再试。",
            "intent": Intent.CLARIFY.value,
            **_fail_state(state, "clarify", "CLARIFY_FAIL", str(exc)),
        }


def retrieval_node(state: GraphState) -> GraphState:
    """RAG 检索节点。

    降级策略：DB 不可用时返回空 chunks，让 answer_node 在无上下文的情况下仍能执行
    （answer_node 自身也有 LLM 降级 → mock 兜底），不阻断整条 RAG 链路。
    """
    try:
        question = state["question"]
        tenant_id = state["tenant_id"]
        chunks = retrieve(question, tenant_id)
        context = format_context(chunks)
        return {**state, "chunks": chunks, "context": context}
    except Exception as exc:
        _log_node_error("retrieval", state, exc)
        return {
            **state,
            "chunks": [],
            "context": "",
            "degraded": True,
            **_fail_state(state, "retrieval", "RETRIEVAL_FAIL",
                          f"检索服务异常：{exc}（已降级为无检索上下文）"),
        }


async def answer_node(state: GraphState) -> AsyncGenerator[GraphState, None]:
    """生成回答节点（流式）。

    降级策略：LLM 全部失败时，用确定性 mock 回答兜底，确保用户总能看到内容。
    不使用全局 try-except 包住整个 async for——只在内部 asyncio.wait_for/provider 调用
    层面让 llm.chat_stream 自己处理降级。但为了防御编程，加一层节点级兜底。
    """
    question = state["question"]
    context = state.get("context", "")
    chunks = state.get("chunks", [])
    trace_id = state.get("trace_id") or ""
    tenant_id = state.get("tenant_id", "")
    history = state.get("history_messages") or []

    # 多轮上下文：system + 历史（最近 10 条）+ 当前 user
    messages: list[dict] = [
        {"role": "system", "content": "你是医疗物资管理智能助手，基于文档内容回答问题，必须引用来源。"
         "上下文包含本会话历史对话，请结合之前的回答保持连贯性。"},
    ]
    if history:
        messages.extend(history[-10:])
    messages.append({"role": "user", "content": question})

    full_answer = ""
    fail_info: dict | None = None
    try:
        async for token in llm.chat_stream(
            messages, context, task="chat", tenant_id=tenant_id, trace_id=trace_id
        ):
            full_answer += token
            yield {**state, "answer": full_answer, "citations": chunks}
    except Exception as exc:
        # 理论上 llm.chat_stream 内部已经全链路降级，这里是最后的防御
        _log_node_error("answer", state, exc)
        mock_lines = ["（当前模型服务暂不可用，以下为确定性兜底回答）"]
        if chunks:
            mock_lines.append(f"检索到 {len(chunks)} 个相关片段，请稍后重试获取基于 AI 的分析。")
        else:
            mock_lines.append("未检索到相关文档，也无法调用模型生成回答。请检查问题描述。")
        full_answer = "\n".join(mock_lines)
        fail_info = _fail_state(state, "answer", "ANSWER_FAIL", str(exc))

    trace = llm.get_trace(trace_id) or {}
    final_update: GraphState = {
        **state,
        "answer": full_answer,
        "citations": chunks,
        "model_used": trace.get("provider", "mock"),
        "model_name": trace.get("model", "mock"),
    }
    if fail_info:
        final_update.update(fail_info)  # type: ignore[typeddict-item]
    yield final_update


async def chat_node(state: GraphState) -> AsyncGenerator[GraphState, None]:
    """自由对话节点（流式）：不检索文档、不查库，直接由模型自然对话。

    用于问候、闲聊、通用问答等未命中业务意图的输入，保证无约束聊天能力；
    同样支持多轮历史，并在模型不可用时用确定性兜底，避免整条链路失败。
    """
    question = state["question"]
    trace_id = state.get("trace_id") or ""
    tenant_id = state.get("tenant_id", "")
    history = state.get("history_messages") or []

    messages: list[dict] = [
        {"role": "system", "content": "你是医疗物资管理智能助手，可以自然地与用户聊天、答疑。"
         "遇到院内制度、流程、数据统计类需求时，可提示用户直接描述业务问题以便精确处理；"
         "保持简洁、友好、专业。"},
    ]
    if history:
        messages.extend(history[-10:])
    messages.append({"role": "user", "content": question})

    full_answer = ""
    fail_info: dict | None = None
    try:
        async for token in llm.chat_stream(
            messages, "", task="chat", tenant_id=tenant_id, trace_id=trace_id
        ):
            full_answer += token
            yield {**state, "answer": full_answer, "citations": []}
    except Exception as exc:
        _log_node_error("chat", state, exc)
        full_answer = "\\n".join([
            "（当前模型服务暂不可用，以下为确定性兜底回答）",
            f"我收到了你的消息：{question[:60]}",
            "请稍后重试，或直接描述要查询的制度文档 / 统计数据。",
        ])
        fail_info = _fail_state(state, "chat", "CHAT_FAIL", str(exc))

    trace = llm.get_trace(trace_id) or {}
    final_update: GraphState = {
        **state,
        "answer": full_answer,
        "citations": [],
        "model_used": trace.get("provider", "mock"),
        "model_name": trace.get("model", "mock"),
    }
    if fail_info:
        final_update.update(fail_info)  # type: ignore[typeddict-item]
    yield final_update


async def nl2sql_node(state: GraphState) -> GraphState:
    """NL2SQL 节点：生成并执行 SQL，返回结构化结果。

    降级策略：run_nl2sql 内部已经把 GuardError / ExecutionError 转为结构化 status，
    外层再补一层兜底——如果 run_nl2sql 本身抛了未预期异常（例如 async 调度层崩溃），
    则返回 status='failed' 的结构化失败 state。
    """
    try:
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
    except Exception as exc:
        _log_node_error("nl2sql", state, exc)
        return {
            **state,
            "sql": "",
            "columns": [],
            "rows": [],
            "row_count": 0,
            "status": "failed",
            "answer": f"数据查询服务异常：{exc}",
            **_fail_state(state, "nl2sql", "NL2SQL_FAIL", str(exc)),
        }


async def report_node(state: GraphState) -> GraphState:
    """报表节点：查询数据 + 构建图表配置。

    降级策略：复用 report_agent.generate_report 已有的 NL2SQL 降级，外层再加兜底。
    """
    try:
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
    except Exception as exc:
        _log_node_error("report", state, exc)
        return {
            **state,
            "sql": "",
            "columns": [],
            "rows": [],
            "row_count": 0,
            "status": "failed",
            "report_title": "数据报表",
            "chart_type": "none",
            "chart_option": {},
            "answer": f"报表生成服务异常：{exc}",
            **_fail_state(state, "report", "REPORT_FAIL", str(exc)),
        }


def review_node(state: GraphState) -> GraphState:
    """Reviewer 节点：质量检查 + 免责声明。

    降级策略：Reviewer 是纯确定性规则（不调 LLM），异常极罕见；
    真异常时跳过 review，原样 answer 通过，保证用户仍能看到答案。
    """
    try:
        review = review_answer(state)
        return {**state, "answer": review["answer"], "review": review}
    except Exception as exc:
        _log_node_error("review", state, exc)
        # 不阻断主链路，返回原始 state（已带上 answer）
        return {
            **state,
            **_fail_state(state, "review", "REVIEW_FAIL",
                          f"质量检查跳过：{exc}（已跳过，保留原始回答）"),
        }


def build_graph():
    """构建 LangGraph。"""
    builder = StateGraph(GraphState)

    builder.add_node("router", router_node)
    builder.add_node("retrieval", retrieval_node)
    builder.add_node("answer", answer_node)
    builder.add_node("chat", chat_node)
    builder.add_node("nl2sql", nl2sql_node)
    builder.add_node("report", report_node)
    builder.add_node("review", review_node)
    builder.add_node("clarify", clarify_node)

    builder.add_edge(START, "router")
    builder.add_conditional_edges("router", route_after_router, {
        "retrieval": "retrieval",
        "nl2sql": "nl2sql",
        "report": "report",
        "chat": "chat",
        "clarify": "clarify",
    })
    builder.add_edge("retrieval", "answer")
    builder.add_edge("answer", "review")
    builder.add_edge("chat", "review")
    builder.add_edge("nl2sql", "review")
    builder.add_edge("report", "review")
    builder.add_edge("review", END)
    builder.add_edge("clarify", END)

    return builder.compile()


graph = build_graph()
