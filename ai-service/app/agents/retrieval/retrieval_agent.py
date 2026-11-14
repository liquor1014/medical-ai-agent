"""检索 Agent：优先 Qdrant 向量相似度，不可用时降级 Postgres ILIKE 关键词匹配。

降级链（设计原则：任何底层组件失败都要返回可用结果，不抛异常给 graph 主链路）：
  1. 调 vector_store.embed(question) → 生成 query vector
  2. 调 vector_store.search(vector, top_k, tenant_id)
  3. 如果 Qdrant 不可用 / embedding 失败 / 返回空 → 走原有 _ilike_retrieve 关键词检索
  4. 关键词检索也返回空 → 返回 []（answer_node 会降级为无上下文 LLM 回答）

两种模式返回统一格式：
  [{"id": ..., "doc_id": ..., "page_no": ..., "section": ...,
    "content": ..., "score": ..., "source": "qdrant" | "ilike"}, ...]
"""
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
    tokens = re.split(r'[\s，。？！、；：,.!?;:\'\"()（）【】\[\]{}]+', question)
    for token in tokens:
        if not token:
            continue
        if any('\u4e00' <= c <= '\u9fff' for c in token):
            for i in range(len(token) - 1):
                keywords.add(token[i:i+2])
        else:
            if len(token) > 2:
                keywords.add(token.lower())
    return list(keywords)


def _ilike_retrieve(question: str, tenant_id: str, top_k: int = 5) -> List[dict]:
    """Postgres ILIKE 关键词匹配（降级兜底）。"""
    keywords = _extract_keywords(question)
    if not keywords:
        return []

    with psycopg.connect(settings.postgres_dsn) as conn:
        with conn.cursor() as cur:
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
        {
            "id": r[0], "doc_id": r[1], "page_no": r[2], "section": r[3],
            "content": r[4], "score": float(r[5]), "source": "ilike",
        }
        for r in rows
    ]
    logger.info("ILIKE 检索到 %d 个片段", len(chunks))
    return chunks


def retrieve(question: str, tenant_id: str, top_k: int = 5) -> List[dict]:
    """优先向量检索，不可用时自动降级 ILIKE 关键词匹配。"""
    # ---------- 1. 尝试向量检索 ----------
    try:
        from app.rag.vector_store import vector_store

        if vector_store.embedding_available and vector_store.health_check():
            query_vector = vector_store.embed([question])
            if query_vector and query_vector[0] and any(abs(v) > 1e-9 for v in query_vector[0]):
                chunks = vector_store.search(
                    vector=query_vector[0],
                    top_k=top_k,
                    tenant_id=tenant_id,
                )
                if chunks:
                    logger.info("Qdrant 向量检索到 %d 个片段 (tenant=%s)", len(chunks), tenant_id)
                    return chunks
                logger.info("Qdrant 返回空结果，降级 ILIKE")
            else:
                logger.info("embedding 返回全零向量，降级 ILIKE")
        else:
            logger.info("Qdrant 或 embedding 不可用，直接降级 ILIKE")
    except Exception as exc:
        # 任何向量检索异常都吞掉，降级关键词
        logger.warning("向量检索异常（降级 ILIKE）: %s", exc)

    # ---------- 2. 降级 ILIKE ----------
    return _ilike_retrieve(question, tenant_id, top_k)


def format_context(chunks: List[dict]) -> str:
    """将检索片段格式化为上下文文本。"""
    if not chunks:
        return ""
    lines = []
    for i, ch in enumerate(chunks, 1):
        score_str = f" score={ch.get('score', 0):.3f}" if "score" in ch else ""
        source = ch.get("source", "")
        source_str = f" [{source}]" if source else ""
        lines.append(
            f"[片段{i}] 文档ID={ch['doc_id']} 页码={ch['page_no']} "
            f"章节={ch['section'] or '无'}{source_str}{score_str}"
        )
        lines.append(ch["content"][:300])
        lines.append("")
    return "\n".join(lines)
