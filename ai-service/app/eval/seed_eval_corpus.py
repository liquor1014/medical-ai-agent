"""写入 Day 8 评测专用语料（租户 eval-bench，固定 ID，幂等重建）。

用法（在 ai-service 目录下执行）：
    python -m app.eval.seed_eval_corpus
"""
from __future__ import annotations

import json
from pathlib import Path

import psycopg

from app.config import settings

REPO_ROOT = Path(__file__).resolve().parents[3]
CORPUS_PATH = REPO_ROOT / "data" / "eval" / "corpus_v1.json"


def seed(corpus_path: Path = CORPUS_PATH) -> dict:
    """按固定 ID 重建评测语料，返回统计信息。"""
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    tenant_id = corpus["tenant_id"]
    documents = corpus["documents"]
    chunk_total = sum(len(d["chunks"]) for d in documents)
    chunk_ids = [int(c["id"]) for d in documents for c in d["chunks"]]

    with psycopg.connect(settings.postgres_dsn) as conn:
        with conn.cursor() as cur:
            # 幂等：先清理该租户的旧语料
            cur.execute("DELETE FROM document_chunk WHERE tenant_id = %s", (tenant_id,))
            cur.execute("DELETE FROM document WHERE tenant_id = %s", (tenant_id,))

            for doc in documents:
                cur.execute(
                    """
                    INSERT INTO document
                        (id, tenant_id, file_name, object_key, doc_type, status, page_count, chunk_count)
                    VALUES (%s, %s, %s, %s, %s, 'parsed', %s, %s)
                    """,
                    (
                        int(doc["id"]), tenant_id, doc["file_name"],
                        f"eval/{tenant_id}/{doc['id']}/{doc['file_name']}",
                        doc.get("doc_type", "unknown"), int(doc.get("page_count", 1)),
                        len(doc["chunks"]),
                    ),
                )
                for ch in doc["chunks"]:
                    cur.execute(
                        """
                        INSERT INTO document_chunk
                            (id, tenant_id, doc_id, page_no, section, content, chunk_type, metadata)
                        VALUES (%s, %s, %s, %s, %s, %s, 'text', '{"source": "eval-bench"}'::jsonb)
                        """,
                        (
                            int(ch["id"]), tenant_id, int(doc["id"]),
                            int(ch.get("page_no", 1)), ch.get("section"),
                            ch["content"],
                        ),
                    )

            # 显式 ID 不推进序列，手动对齐，避免后续自增冲突
            cur.execute(
                "SELECT setval('document_id_seq', (SELECT GREATEST(MAX(id), 1) FROM document))"
            )
            cur.execute(
                "SELECT setval('document_chunk_id_seq', (SELECT GREATEST(MAX(id), 1) FROM document_chunk))"
            )
        conn.commit()

    return {
        "tenant_id": tenant_id,
        "documents": len(documents),
        "chunks": chunk_total,
        "chunk_id_min": min(chunk_ids),
        "chunk_id_max": max(chunk_ids),
    }


if __name__ == "__main__":
    print(json.dumps(seed(), ensure_ascii=False, indent=2))
