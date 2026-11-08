"""意图路由：基于关键词规则分类，后续可替换为小模型分类。"""
from __future__ import annotations

import logging
from enum import Enum

logger = logging.getLogger(__name__)


class Intent(str, Enum):
    RETRIEVAL = "retrieval"      # 文件问答 / RAG
    NL2SQL = "nl2sql"            # 数据查询 / 统计
    REPORT = "report"            # 生成报表 / 图表
    CLARIFY = "clarify"          # 意图不清，需追问


_RETRIEVAL_KEYWORDS = [
    "文件", "制度", "合同", "规定", "流程", "第几页", "内容", "文档", "条款", "办法",
    "规程", "规范", "预案", "标准", "要求", "职责", "审批", "审议", "公示", "申请",
    "验收", "入库", "上架", "退库", "扫码", "计费", "储运", "运输", "冷链", "温度",
    "灭菌", "消毒", "有效期", "保存", "存放", "标识", "追溯", "准入", "绩效", "储备",
    "损耗", "对账", "结算", "补货", "到货", "质保金", "零库存", "比价", "资质",
    "检测", "应急", "储罐", "补液", "计划",
]
_NL2SQL_KEYWORDS = [
    "多少", "数量", "趋势", "排名", "同比", "环比", "占比", "统计", "汇总", "平均",
    "总额", "金额", "合计", "采购量", "采购额", "库存", "库存量", "库存数量", "库存预警",
    "查询", "列出", "返回", "排序", "最高", "最低", "低于", "高于",
]
_REPORT_KEYWORDS = ["报表", "图", "图表", "可视化", "生成报表", "导出"]


def classify(question: str) -> Intent:
    """按“报表 > 文档问答 > 数据查询”的优先级匹配，默认走文档问答。

    文档类关键词优先于 SQL 关键词：含“多少”的制度类问题（如“灭菌时间是多少”）
    应走 RAG，而不是被当成统计查询。
    """
    q = question.lower()
    if any(kw in q for kw in _REPORT_KEYWORDS):
        return Intent.REPORT
    if any(kw in q for kw in _RETRIEVAL_KEYWORDS):
        return Intent.RETRIEVAL
    if any(kw in q for kw in _NL2SQL_KEYWORDS):
        return Intent.NL2SQL
    return Intent.RETRIEVAL
