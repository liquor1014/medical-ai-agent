"""Reviewer Agent：回答生成后的确定性质量检查（Day 7）。

检查项：
- 回答非空；
- 文件问答必须带引用（页码可追溯）；
- SQL / 报表类回答必须执行成功且 SQL 只读；
- 报表有数据时必须带图表配置；
- 医疗内容追加“非诊疗建议”免责声明。
"""
from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)

DISCLAIMER = "\n\n（以上内容基于院内文档与统计数据分析，仅供管理参考，不构成诊疗建议。）"


def _needs_disclaimer(state: dict) -> bool:
    intent = state.get("intent")
    answer = state.get("answer") or ""
    if intent not in ("retrieval", "nl2sql", "report"):
        return False
    return "不构成诊疗建议" not in answer


def review_answer(state: dict) -> dict:
    """审查一次回答，返回 {passed, issues, level, answer, provider, reviewed_at}。"""
    intent = state.get("intent") or "retrieval"
    answer = (state.get("answer") or "").strip()
    citations = state.get("citations") or []
    issues: list[str] = []

    if not answer:
        issues.append("回答为空")

    if intent == "retrieval" and not citations:
        issues.append("文件问答缺少引用来源")

    if intent in ("nl2sql", "report"):
        status = state.get("status")
        if status and status != "success":
            issues.append(f"数据查询状态异常：{status}")
        sql = (state.get("sql") or "").strip()
        if sql and not sql.lstrip().upper().startswith("SELECT"):
            issues.append("SQL 不是只读查询")

    if intent == "report" and state.get("rows") and not state.get("chart_option"):
        issues.append("报表缺少图表配置")

    final_answer = answer
    if _needs_disclaimer(state) and answer:
        final_answer = answer + DISCLAIMER

    passed = not issues
    result = {
        "passed": passed,
        "level": "pass" if passed else "warn",
        "issues": issues,
        "answer": final_answer,
        "provider": state.get("model_used"),
        "reviewed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    if issues:
        logger.warning("Reviewer 发现问题: intent=%s issues=%s", intent, issues)
    else:
        logger.info("Reviewer 通过: intent=%s provider=%s", intent, state.get("model_used"))
    return result
