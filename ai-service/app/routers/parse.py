"""文档解析接口：下载 -> 结构化解析 -> 分块 -> 入库(Postgres) + 向量化(Qdrant)。"""
from __future__ import annotations

import json
import logging
import mimetypes
import uuid
from typing import List

import psycopg
from fastapi import APIRouter, HTTPException
from minio import Minio
from pydantic import BaseModel

from app.config import settings
from app.llm.providers import llm
from app.rag.chunker import chunk_blocks
from app.rag.parser import IMAGE_EXTENSIONS, ParsedBlock, parse_blocks
from app.rag.vector_store import vector_store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["parse"])


class ParseRequest(BaseModel):
    doc_id: int
    object_key: str
    tenant_id: str
    doc_type: str = "unknown"


class ParseResponse(BaseModel):
    doc_id: int
    page_count: int
    chunk_count: int
    text_count: int = 0
    table_count: int = 0
    image_count: int = 0


def _minio_client() -> Minio:
    return Minio(
        settings.minio_endpoint.replace("http://", "").replace("https://", ""),
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_endpoint.startswith("https"),
    )


def _pg_conn():
    return psycopg.connect(settings.postgres_dsn)


def _is_image_file(file_name: str) -> bool:
    return file_name.lower().endswith(IMAGE_EXTENSIONS)


@router.post("/parse", response_model=ParseResponse)
async def parse_document(req: ParseRequest) -> ParseResponse:
    logger.info("开始解析文档: doc_id=%s, object_key=%s", req.doc_id, req.object_key)

    # 1. 从 MinIO 下载文件
    try:
        client = _minio_client()
        resp = client.get_object(settings.minio_bucket, req.object_key)
        file_bytes = resp.read()
        resp.close()
        resp.release_conn()
    except Exception as e:
        logger.error("MinIO 下载失败: %s", e)
        raise HTTPException(status_code=500, detail=f"MinIO 下载失败: {e}")

    file_name = req.object_key.rsplit("/", 1)[-1]

    # 2. 多模态解析（文本 / 表格 / 图片 / 扫描页）
    blocks = parse_blocks(file_bytes, file_name)
    page_count = max({b.page_no for b in blocks}) if blocks else 0
    logger.info("解析得到 %d 页, %d 个结构化块", page_count, len(blocks))

    # 3. 多模态兜底：纯图片且本地 OCR 未识别时，调用视觉模型
    if llm.vision_available and _is_image_file(file_name):
        for block in blocks:
            if block.block_type == "image" and block.metadata.get("engine") == "none":
                mime = mimetypes.guess_type(file_name)[0] or "image/png"
                description = await llm.vision_describe(file_bytes, mime)
                if description:
                    block.content = description
                    block.metadata["engine"] = "vision"

    # 4. 分块
    chunks = chunk_blocks(blocks)
    chunk_count = len(chunks)
    text_count = sum(1 for c in chunks if c.chunk_type == "text")
    table_count = sum(1 for c in chunks if c.chunk_type == "table")
    image_count = sum(1 for c in chunks if c.chunk_type == "image")
    logger.info("分块得到 %d 块（文本 %d / 表格 %d / 图片 %d）",
                chunk_count, text_count, table_count, image_count)

    # 5. 写入 Postgres document_chunk 表
    try:
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                for ch in chunks:
                    embedding_id = str(uuid.uuid4())
                    cur.execute(
                        """
                        INSERT INTO document_chunk
                            (tenant_id, doc_id, page_no, section, content, embedding_id,
                             chunk_type, metadata)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                        """,
                        (
                            req.tenant_id, req.doc_id, ch.page_no, ch.section,
                            ch.content, embedding_id, ch.chunk_type,
                            json.dumps(ch.metadata or {}, ensure_ascii=False),
                        ),
                    )
            conn.commit()
        logger.info("document_chunk 写入完成: %d 条", chunk_count)
    except Exception as e:
        logger.error("写入 document_chunk 失败: %s", e)
        raise HTTPException(status_code=500, detail=f"写入数据库失败: {e}")

    # 6. 向量化并写入 Qdrant（embedding 模型不可用时跳过）
    _store_vectors(req, chunks)

    return ParseResponse(
        doc_id=req.doc_id,
        page_count=page_count,
        chunk_count=chunk_count,
        text_count=text_count,
        table_count=table_count,
        image_count=image_count,
    )


def _store_vectors(req: ParseRequest, chunks: List) -> None:
    """尝试生成 embedding 并写入 Qdrant；模型不可用时静默跳过。"""
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore

        model = SentenceTransformer("all-MiniLM-L6-v2")
        dim = model.get_sentence_embedding_dimension()
        vector_store.ensure_collection(dim)

        if not vector_store.available:
            logger.info("Qdrant 不可用，跳转向量化")
            return

        texts = [ch.content for ch in chunks]
        embeddings = model.encode(texts, show_progress_bar=False)

        from qdrant_client.http.models import PointStruct

        points = [
            PointStruct(
                id=idx + 1,
                vector=emb.tolist(),
                payload={
                    "doc_id": req.doc_id,
                    "tenant_id": req.tenant_id,
                    "page_no": ch.page_no,
                    "section": ch.section,
                    "content": ch.content,
                    "chunk_type": ch.chunk_type,
                },
            )
            for idx, (ch, emb) in enumerate(zip(chunks, embeddings))
        ]
        vector_store.upsert(points)
        logger.info("Qdrant 写入完成: %d 个向量", len(points))
    except ImportError:
        logger.info("sentence-transformers 未安装，跳过向量存储（仅文本检索可用）")
    except Exception as e:
        logger.warning("向量化失败（不影响文本入库）: %s", e)
