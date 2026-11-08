"""NL2SQL Agent：自然语言生成 SQL、安全校验、执行与审计落库。"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import date, datetime
from decimal import Decimal

import psycopg

from app.agents.nl2sql.schema import SCHEMA_DESCRIPTION, SQL_RULES
from app.agents.nl2sql.sql_guard import GuardError, guard_sql
from app.config import settings
from app.llm.providers import llm

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "你是医疗物资管理系统的 SQL 生成助手。根据用户问题生成 PostgreSQL 查询语句。\n"
    f"{SCHEMA_DESCRIPTION}\n{SQL_RULES}"
)


class ExecutionError(Exception):
    """SQL 执行失败。"""


def _mock_generate_sql(question: str) -> str:
    """无 LLM Key 时基于关键词规则生成演示 SQL。"""
    q = question

    if any(k in q for k in ("库存", "积压", "预警")):
        return (
            'SELECT i.name AS "物资名称", i.category AS "类别", '
            'SUM(inv.qty) AS "库存量", i.unit_price AS "单价" '
            "FROM inventory inv JOIN item i ON inv.item_id = i.id "
            'GROUP BY i.name, i.category, i.unit_price ORDER BY "库存量" DESC'
        )

    if any(k in q for k in ("供应商", "履约", "到货率")):
        return (
            'SELECT s.name AS "供应商", COUNT(po.id) AS "订单数", '
            'SUM(po.amount) AS "采购总额", s.fulfillment_rate AS "履约率" '
            "FROM supplier s LEFT JOIN purchase_order po ON po.supplier_id = s.id "
            'GROUP BY s.name, s.fulfillment_rate ORDER BY "采购总额" DESC'
        )

    if any(k in q for k in ("科室", "消耗", "领用", "用量")):
        return (
            'SELECT d.name AS "科室", SUM(c.amount) AS "消耗金额", SUM(c.qty) AS "消耗数量" '
            "FROM consumption c JOIN department d ON c.dept_id = d.id "
            'GROUP BY d.name ORDER BY "消耗金额" DESC'
        )

    if any(k in q for k in ("趋势", "月度", "每月", "月份")):
        return (
            "SELECT to_char(po.order_date, 'YYYY-MM') AS \"月份\", "
            'SUM(po.amount) AS "采购金额", COUNT(*) AS "订单数" '
            "FROM purchase_order po GROUP BY \"月份\" ORDER BY \"月份\""
        )

    if any(k in q for k in ("本月", "上月", "今年", "本年")):
        return (
            'SELECT SUM(po.amount) AS "采购总额", COUNT(*) AS "订单数" '
            "FROM purchase_order po "
            "WHERE po.order_date >= date_trunc('month', CURRENT_DATE)"
        )

    if any(k in q for k in ("采购", "金额", "总额", "花费")):
        return (
            'SELECT to_char(po.order_date, \'YYYY-MM\') AS "月份", '
            'SUM(po.amount) AS "采购金额" '
            "FROM purchase_order po GROUP BY \"月份\" ORDER BY \"月份\""
        )

    return (
        'SELECT po.id AS "订单号", s.name AS "供应商", po.amount AS "金额", '
        'po.status AS "状态", po.order_date AS "下单日期" '
        "FROM purchase_order po JOIN supplier s ON po.supplier_id = s.id "
        'ORDER BY po.order_date DESC'
    )


async def generate_sql(
    question: str, tenant_id: str, trace_id: str = "", task: str = "nl2sql"
) -> str:
    """生成 SQL。真实模型失败时降级为规则模板。"""
    if not llm.has_real_provider(task):
        return _mock_generate_sql(question)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    sql = await llm.chat(
        messages, task=task, tenant_id=tenant_id, trace_id=trace_id
    )
    if sql:
        return sql
    logger.warning("LLM 未返回 SQL，降级为规则模板")
    return _mock_generate_sql(question)


def _to_json_value(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def execute_sql(guarded_sql: str) -> tuple[list[str], list[dict]]:
    """在只读连接中执行 SQL，返回列名与行数据。"""
    try:
        with psycopg.connect(settings.postgres_dsn, connect_timeout=5) as conn:
            conn.read_only = True
            conn.execute("SET statement_timeout = '5s'")
            with conn.cursor() as cur:
                cur.execute(guarded_sql)
                columns = [d.name for d in cur.description or []]
                raw_rows = cur.fetchall()
    except Exception as e:
        raise ExecutionError(str(e)) from e

    rows = [
        {col: _to_json_value(val) for col, val in zip(columns, row)}
        for row in raw_rows
    ]
    return columns, rows


def _summarize(columns: list[str], rows: list[dict]) -> str:
    """生成简短结论（无 LLM 时的确定性摘要）。"""
    if not rows:
        return "查询已执行，但没有匹配的数据。"
    if len(rows) == 1 and len(columns) <= 3:
        parts = [f"{col}: {rows[0][col]}" for col in columns]
        return "查询结果：" + "，".join(parts)
    return f"查询完成，共返回 {len(rows)} 行结果（字段：{'、'.join(columns)}）。"


def _write_logs(
    tenant_id: str,
    question: str,
    sql: str,
    status: str,
    columns: list[str],
    rows: list[dict],
) -> int | None:
    """写入 report_query 与 audit_log（独立连接，非只读），返回 report_query 主键。"""
    sql_hash = hashlib.sha256(sql.encode("utf-8")).hexdigest()
    result_payload = json.dumps(
        {"columns": columns, "rows": rows}, ensure_ascii=False, default=str
    )
    try:
        with psycopg.connect(settings.postgres_dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO report_query (tenant_id, user_id, question, sql, status, result)
                    VALUES (%s, 0, %s, %s, %s, %s::jsonb)
                    RETURNING id
                    """,
                    (tenant_id, question, sql, status, result_payload),
                )
                report_id = cur.fetchone()[0]
                cur.execute(
                    """
                    INSERT INTO audit_log (tenant_id, user_id, action, sql_hash, result)
                    VALUES (%s, 0, 'nl2sql', %s, %s)
                    """,
                    (tenant_id, sql_hash, status),
                )
            conn.commit()
            return report_id
    except Exception:
        logger.exception("NL2SQL 审计日志写入失败")
        return None


def update_report_chart_type(report_id: int, chart_type: str) -> None:
    """回写报表图表类型。"""
    try:
        with psycopg.connect(settings.postgres_dsn) as conn:
            conn.execute(
                "UPDATE report_query SET chart_type = %s WHERE id = %s",
                (chart_type, report_id),
            )
            conn.commit()
    except Exception:
        logger.exception("回写 chart_type 失败: report_id=%s", report_id)


async def run_nl2sql(
    question: str, tenant_id: str, trace_id: str = "", task: str = "nl2sql"
) -> dict:
    """NL2SQL 主流程：生成 → 校验 → 执行 → 审计。

    返回包含 sql / columns / rows / answer / status 的字典。
    """
    sql = await generate_sql(question, tenant_id, trace_id, task=task)
    logger.info("NL2SQL 生成: %s", sql)

    try:
        guarded = guard_sql(sql, tenant_id)
    except GuardError as e:
        logger.warning("SQL 校验失败: %s", e)
        report_id = _write_logs(tenant_id, question, sql, "rejected", [], [])
        return {
            "sql": sql,
            "columns": [],
            "rows": [],
            "answer": f"SQL 安全校验未通过：{e}",
            "status": "rejected",
            "report_id": report_id,
        }

    try:
        columns, rows = execute_sql(guarded)
    except ExecutionError as e:
        logger.warning("SQL 执行失败: %s", e)
        report_id = _write_logs(tenant_id, question, sql, "failed", [], [])
        return {
            "sql": guarded,
            "columns": [],
            "rows": [],
            "answer": f"SQL 执行失败：{e}",
            "status": "failed",
            "report_id": report_id,
        }

    answer = _summarize(columns, rows)
    report_id = _write_logs(tenant_id, question, sql, "success", columns, rows)
    collect_citation = {
        "type": "sql",
        "sql": sql,
        "row_count": len(rows),
    }
    return {
        "sql": guarded,
        "columns": columns,
        "rows": rows,
        "answer": answer,
        "status": "success",
        "report_id": report_id,
        "citations": [collect_citation],
    }
