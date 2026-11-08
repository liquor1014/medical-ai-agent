"""报表 Agent：基于 NL2SQL 结果生成标题、ECharts 图表配置与摘要。"""
from __future__ import annotations

import logging
import re

from app.agents.nl2sql.nl2sql_agent import run_nl2sql, update_report_chart_type

logger = logging.getLogger(__name__)

_TITLE_RULES = [
    ("库存", "库存报表"),
    ("供应商", "供应商报表"),
    ("科室", "科室消耗报表"),
    ("消耗", "科室消耗报表"),
    ("领用", "科室消耗报表"),
    ("采购", "采购报表"),
]


def _pick_title(question: str) -> str:
    for kw, title in _TITLE_RULES:
        if kw in question:
            return title
    return "数据报表"


def _numeric_columns(columns: list[str], rows: list[dict]) -> list[str]:
    numeric = [
        c for c in columns[1:]
        if rows and all(isinstance(r.get(c), (int, float)) and not isinstance(r.get(c), bool) for r in rows)
    ]
    # 单价、价格、比率类字段不作为图表度量（避免和数量/金额混在同一坐标轴）
    preferred = [c for c in numeric if not any(k in c for k in ("单价", "价格", "率"))]
    return preferred or numeric


def _pick_value_column(numeric_cols: list[str]) -> str | None:
    for c in numeric_cols:
        if "金额" in c or "总额" in c:
            return c
    for c in numeric_cols:
        if "数量" in c or "库存" in c:
            return c
    return numeric_cols[0] if numeric_cols else None


def build_chart(question: str, columns: list[str], rows: list[dict]) -> tuple[str, dict]:
    """根据数据形态选择图表类型并生成 ECharts option。"""
    title = _pick_title(question)
    if not columns or not rows:
        return "none", {"title": {"text": title}, "series": []}

    categories = [str(r.get(columns[0], "")) for r in rows]
    numeric_cols = _numeric_columns(columns, rows)
    if not numeric_cols:
        return "none", {"title": {"text": title}, "series": []}

    is_month_trend = all(re.fullmatch(r"\d{4}-\d{2}", c) for c in categories)
    wants_pie = any(k in question for k in ("占比", "分布", "比例")) and len(rows) <= 10

    if is_month_trend:
        chart_type = "line"
    elif wants_pie:
        chart_type = "pie"
    else:
        chart_type = "bar"

    if chart_type == "pie":
        value_col = _pick_value_column(numeric_cols)
        option = {
            "title": {"text": title, "left": "center"},
            "tooltip": {"trigger": "item", "formatter": "{b}: {c} ({d}%)"},
            "legend": {"orient": "vertical", "right": 10, "top": "middle"},
            "series": [{
                "name": title,
                "type": "pie",
                "radius": ["35%", "65%"],
                "center": ["45%", "55%"],
                "data": [
                    {"name": cat, "value": row.get(value_col)}
                    for cat, row in zip(categories, rows)
                ],
                "emphasis": {"itemStyle": {"shadowBlur": 10}},
            }],
        }
    else:
        option = {
            "title": {"text": title, "left": "center"},
            "tooltip": {"trigger": "axis"},
            "legend": {"top": 30, "data": numeric_cols},
            "grid": {"left": 60, "right": 30, "bottom": 60, "top": 70},
            "xAxis": {
                "type": "category",
                "data": categories,
                "axisLabel": {"rotate": 30, "interval": 0},
            },
            "yAxis": {"type": "value"},
            "series": [
                {
                    "name": col,
                    "type": chart_type,
                    "smooth": chart_type == "line",
                    "areaStyle": {"opacity": 0.15} if chart_type == "line" else None,
                    "data": [row.get(col) for row in rows],
                }
                for col in numeric_cols
            ],
        }
    return chart_type, option


def _summarize(title: str, columns: list[str], rows: list[dict], chart_type: str) -> str:
    if not rows:
        return f"{title}已生成，但当前没有可展示的数据。"
    numeric_cols = _numeric_columns(columns, rows)
    value_col = _pick_value_column(numeric_cols)
    best = max(rows, key=lambda r: r.get(value_col) or 0) if value_col else rows[0]
    highlight = ""
    if value_col:
        highlight = f"，最高为{best.get(columns[0])}（{value_col} {best.get(value_col)}）"
    hint = {"line": "趋势折线图", "pie": "占比饼图", "bar": "排名柱状图"}.get(chart_type, "表格")
    return f"{title}已生成，共 {len(rows)} 项{highlight}。图表类型：{hint}。"


async def generate_report(question: str, tenant_id: str, trace_id: str = "") -> dict:
    """生成报表：执行数据查询 + 构建图表配置 + 回写图表类型。"""
    result = await run_nl2sql(question, tenant_id, trace_id, task="report")
    title = _pick_title(question)
    chart_type, option = build_chart(question, result["columns"], result["rows"])
    summary = _summarize(title, result["columns"], result["rows"], chart_type)

    report_id = result.get("report_id")
    if report_id and chart_type != "none":
        update_report_chart_type(report_id, chart_type)

    logger.info("报表生成: title=%s, chart_type=%s, report_id=%s, rows=%d",
                title, chart_type, report_id, len(result["rows"]))
    return {
        **result,
        "report_id": report_id,
        "report_title": title,
        "chart_type": chart_type,
        "chart_option": option,
        "summary": summary,
    }
