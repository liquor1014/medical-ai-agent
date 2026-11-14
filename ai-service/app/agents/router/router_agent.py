"""意图路由：基于关键词规则分类，后续可替换为小模型分类。"""
from __future__ import annotations

import logging
import re
from enum import Enum

logger = logging.getLogger(__name__)


class Intent(str, Enum):
    RETRIEVAL = "retrieval"      # 文件问答 / RAG
    NL2SQL = "nl2sql"            # 数据查询 / 统计
    REPORT = "report"            # 生成报表 / 图表
    CHAT = "chat"                # 自由对话 / 闲聊 / 通用问题（默认分支）
    CLARIFY = "clarify"          # 真歧义，需追问


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
    """按“报表 > 文档问答 > 数据查询 > 自由对话”的优先级匹配。

    澄清（CLARIFY）只在两种真正无法判断的情况下触发：
      1. 输入没有语义（空 / 纯符号数字 / 单字符）；
      2. 同时命中文档类和数据类关键词（如“灭菌时间是多少”），
         无法确定用户要查文档还是查统计。
    其余未命中任何业务关键词的输入一律走 CHAT 自由对话，
    避免闲聊、问候、通用问题被强制拖入意图确认流程。
    """
    stripped = question.strip()
    # 无语义检测：空 / 纯符号数字 / 长度过短
    if not stripped:
        return Intent.CLARIFY
    if len(re.sub(r"\s+", "", stripped)) < 2:
        return Intent.CLARIFY
    if re.fullmatch(r"[\d\s\W_]+", stripped):
        return Intent.CLARIFY

    q = stripped.lower()
    hit_retrieval = any(kw in q for kw in _RETRIEVAL_KEYWORDS)
    hit_nl2sql = any(kw in q for kw in _NL2SQL_KEYWORDS)
    hit_report = any(kw in q for kw in _REPORT_KEYWORDS)

    if hit_report:
        return Intent.REPORT
    # 同时命中文档 + 数据类关键词，属于真歧义 → 澄清
    if hit_retrieval and hit_nl2sql:
        return Intent.CLARIFY
    if hit_retrieval:
        return Intent.RETRIEVAL
    if hit_nl2sql:
        return Intent.NL2SQL
    # 未命中任何业务关键词 → 自由对话（问候、闲聊、通用问答）
    return Intent.CHAT
