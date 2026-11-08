"""检索 Agent：从 Postgres document_chunk 表检索相关片段。"""
from __future__ import annotations

import logging
import re
from typing import List

import psycopg

from app.config import settings

logger = logging.getLogger(__name__)


def _extract_keywords(question: str) -> List[str]:
    """从问题中提取关键词：中文按 2-char bigram，英文按空格分词。"""
    keywords = set()
    # 先按空格/标点切分
    tokens = re.split(r'[\s，。？！、；：,.!?;:\'\"()（）【】\[\]{}]+', question)
    for token in tokens:
        if not token:
            continue
        # 中文：生成 2-char bigram
        if any('\u4e00' <= c <= '\u9fff' for c in token):
            for i in range(len(token) - 1):
                keywords.add(token[i:i+2])
        else:
            # 英文：长度 > 2 的词
            if len(token) > 2:
                keywords.add(token.lower())
    return list(keywords)


def retrieve(question: str, tenant_id: str, top_k: int = 5) -> List[dict]:
    """简单关键词检索（embedding 不可用时的降级方案）。"""
    keywords = _extract_keywords(question)
    if not keywords:
        return []

    with psycopg.connect(settings.postgres_dsn) as conn:
        with conn.cursor() as cur:
            # 用 ILIKE 做关键词匹配，按命中的关键词数量排序（同分时新片段优先）
            ilike_params = [f"%{kw}%" for kw in keywords]
            conditions = " OR ".join(["content ILIKE %s"] * len(keywords))
            score_expr = " + ".join(
                ["(CASE WHEN content ILIKE %s THEN 1 ELSE 0 END)"] * len(keywords)
            )
            params = ilike_params + ilike_params + [tenant_id, top_k]
            cur.execute(
                f"""
                SELECT id, doc_id, page_no, section, content,
                       ({score_expr}) AS hit_score
                FROM document_chunk
                WHERE ({conditions}) AND tenant_id = %s
                ORDER BY hit_score DESC, id DESC
                LIMIT %s
                """,
                params,
            )
            rows = cur.fetchall()

    chunks = [
        {"id": r[0], "doc_id": r[1], "page_no": r[2], "section": r[3], "content": r[4]}
        for r in rows
    ]
    logger.info("检索到 %d 个片段", len(chunks))
    return chunks


def format_context(chunks: List[dict]) -> str:
    """将检索片段格式化为上下文文本。"""
    if not chunks:
        return ""
    lines = []
    for i, ch in enumerate(chunks, 1):
        lines.append(f"[片段{i}] 文档ID={ch['doc_id']} 页码={ch['page_no']} 章节={ch['section'] or '无'}")
        lines.append(ch["content"][:300])
        lines.append("")
    return "\n".join(lines)
