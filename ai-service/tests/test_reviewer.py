"""Reviewer Agent 质量检查测试。"""
from __future__ import annotations

from app.agents.reviewer.reviewer_agent import DISCLAIMER, review_answer


def test_retrieval_without_citation_is_flagged() -> None:
    review = review_answer({
        "intent": "retrieval",
        "answer": "根据制度，高值耗材需要双人核对。",
        "citations": [],
    })
    assert review["passed"] is False
    assert any("引用" in issue for issue in review["issues"])


def test_retrieval_with_citation_passes_and_adds_disclaimer() -> None:
    review = review_answer({
        "intent": "retrieval",
        "answer": "根据制度，高值耗材需要双人核对。",
        "citations": [{"doc_id": 1, "page_no": 3}],
    })
    assert review["passed"] is True
    assert review["answer"].endswith(DISCLAIMER)


def test_nl2sql_failed_status_and_write_sql_are_flagged() -> None:
    review = review_answer({
        "intent": "nl2sql",
        "answer": "执行失败",
        "status": "failed",
        "sql": "DELETE FROM inventory",
        "citations": [{"type": "sql"}],
    })
    assert review["passed"] is False
    assert any("状态异常" in issue for issue in review["issues"])
    assert any("只读" in issue for issue in review["issues"])


def test_report_missing_chart_is_flagged() -> None:
    review = review_answer({
        "intent": "report",
        "answer": "报表已生成",
        "status": "success",
        "sql": "SELECT 1",
        "rows": [{"a": 1}],
        "chart_option": None,
        "citations": [{"type": "report"}],
    })
    assert review["passed"] is False
    assert any("图表" in issue for issue in review["issues"])
