"""Qdrant 向量存储封装。

对外接口（必须保持兼容 parse.py / retrieval_agent.py 的调用方式）：
  - vector_store.available           → bool
  - vector_store.ensure_collection(dim)
  - vector_store.upsert(points)
  - vector_store.search(vector, top_k, tenant_id) → List[dict]  ← 新增
  - vector_store.health_check()       → bool                     ← 新增
  - vector_store.embed(texts)        → List[List[float]]         ← 新增
  - vector_store.rebuild_collection()                              ← 新增

降级链：parse / retrieval 调用方只依赖 vector_store.search()，
它内部自动处理 Qdrant 连接失败、collection 不存在、embedding 不可用，
返回空列表让 retrieval_agent 自动走到 ILIKE 关键词检索兜底。
"""
from __future__ import annotations

import functools
import logging
import random
import time
from typing import Callable, List, Optional

from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from app.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 重试装饰器：Qdrant 瞬时连接/超时异常自动重试
# ---------------------------------------------------------------------------

def _with_retry(description: str, max_retries: int | None = None) -> Callable:
    """给 Qdrant 调用加 N 次重试；重试耗尽后返回 None（不抛给上层，让上层走降级）。"""
    retries = max_retries if max_retries is not None else settings.qdrant_retries

    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exc: Optional[Exception] = None
            for attempt in range(retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:
                    last_exc = exc
                    if attempt < retries:
                        logger.warning(
                            "[Qdrant %s] 第 %d 次失败，%.1fs 后重试: %s",
                            description, attempt + 1, 0.5 * (attempt + 1), exc,
                        )
                        time.sleep(0.5 * (attempt + 1))
                    else:
                        logger.warning(
                            "[Qdrant %s] 重试耗尽 (%d 次)，返回 None: %s",
                            description, retries + 1, exc,
                        )
                        return None
            assert last_exc is None  # 不会到这里
            return None
        return wrapper
    return decorator


class VectorStore:
    """Qdrant 向量存储客户端 + Embedding 客户端。

    初始化时连不上 Qdrant 或 embedding 模型不可用都不抛异常，
    只把 available 标志置为 False，search() 自动返回空列表让上层走 ILIKE。
    """

    def __init__(self) -> None:
        self.client: Optional[QdrantClient] = None
        self.embedding_dim = settings.qdrant_embedding_dim
        self._embedding_model = None
        self._init_client()
        self._init_embedding()

    # ------------------------------------------------------------------
    # 初始化 / 健康检查
    # ------------------------------------------------------------------

    def _init_client(self) -> None:
        try:
            # timeout 只在构造函数传，后续所有方法自动继承
            self.client = QdrantClient(
                url=settings.qdrant_url,
                timeout=int(settings.qdrant_timeout),
            )
            _ = self.client.get_collections()
            logger.info("Qdrant 连接成功: %s (timeout=%ds)", settings.qdrant_url, settings.qdrant_timeout)
        except Exception as exc:
            logger.warning("Qdrant 连接失败（将降级为文本检索）: %s", exc)
            self.client = None

    def _init_embedding(self) -> None:
        """懒加载 embedding 模型；import 失败或 backend='mock' 时置为 None。"""
        backend = settings.embedding_backend
        if backend == "mock":
            logger.info("embedding_backend=mock，使用随机向量占位")
            self._embedding_model = None
            return
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore

            self._embedding_model = SentenceTransformer(settings.embedding_model_name)
            self.embedding_dim = self._embedding_model.get_sentence_embedding_dimension()
            logger.info("embedding 模型加载成功: %s (dim=%d)", settings.embedding_model_name, self.embedding_dim)
        except ImportError:
            logger.warning("sentence-transformers 未安装（将降级为文本检索）")
            self._embedding_model = None
        except Exception as exc:
            logger.warning("embedding 模型加载失败: %s", exc)
            self._embedding_model = None

    def health_check(self) -> bool:
        """返回 Qdrant 服务是否健康可达。"""
        if self.client is None:
            return False
        try:
            _ = self.client.get_collections()
            return True
        except Exception as exc:
            logger.warning("health_check 失败: %s", exc)
            # 尝试重建客户端（可能是连接池耗尽）
            self.client = None
            self._init_client()
            return self.client is not None

    # ------------------------------------------------------------------
    # 属性 / 可用性
    # ------------------------------------------------------------------

    @property
    def embedding_available(self) -> bool:
        return self._embedding_model is not None or settings.embedding_backend == "mock"

    @property
    def available(self) -> bool:
        """parse.py 的 _store_vectors 用这个判断是否写入。"""
        return self.client is not None and self.embedding_available

    # ------------------------------------------------------------------
    # Collection 管理
    # ------------------------------------------------------------------

    @_with_retry("ensure_collection")
    def ensure_collection(self, dim: int | None = None) -> None:
        """确保 collection 存在；dim 优先用参数，否则用配置默认值。"""
        if self.client is None:
            return
        effective_dim = dim or self.embedding_dim
        if not effective_dim:
            logger.warning("ensure_collection dim=0，跳过")
            return
        self.embedding_dim = effective_dim
        collections = [c.name for c in self.client.get_collections().collections]
        if settings.qdrant_collection not in collections:
            self.client.create_collection(
                collection_name=settings.qdrant_collection,
                vectors_config=VectorParams(size=effective_dim, distance=Distance.COSINE),
            )
            # 为 tenant_id / doc_id 建 payload 索引（加速 filter）
            try:
                from qdrant_client.http.models import PayloadSchemaType
                self.client.create_payload_index(
                    collection_name=settings.qdrant_collection,
                    field_name="tenant_id",
                    field_schema=PayloadSchemaType.KEYWORD,
                )
                self.client.create_payload_index(
                    collection_name=settings.qdrant_collection,
                    field_name="doc_id",
                    field_schema=PayloadSchemaType.INTEGER,
                )
                logger.info("Qdrant collection %s 已创建 (dim=%d, payload 索引已建)",
                            settings.qdrant_collection, effective_dim)
            except Exception as exc:
                # payload 索引创建失败不影响 collection 可用性
                logger.warning("payload 索引创建失败（忽略）: %s", exc)
        else:
            # 已存在 → 校验维度是否一致（不一致打警告但不重建，避免丢数据）
            info = self.client.get_collection(settings.qdrant_collection)
            existing_dim = getattr(info.config.params.vectors, "size", 0)
            if existing_dim != effective_dim:
                logger.warning(
                    "Qdrant collection 维度不匹配: 现有=%d, 期望=%d。"
                    "向量会因维度不匹配被 Qdrant 拒绝写入，需先 rebuild。",
                    existing_dim, effective_dim,
                )
            else:
                logger.info("Qdrant collection %s 已存在 (dim=%d)，复用", settings.qdrant_collection, effective_dim)

    def rebuild_collection(self) -> None:
        """删除并重建 collection（维度变更时用；会清空所有向量数据）。"""
        if self.client is None:
            logger.warning("Qdrant 不可用，无法 rebuild")
            return
        try:
            self.client.delete_collection(collection_name=settings.qdrant_collection)
            logger.warning("Qdrant collection %s 已删除，将重新创建", settings.qdrant_collection)
        except Exception as exc:
            logger.warning("delete_collection 失败: %s", exc)
        self.ensure_collection(self.embedding_dim)

    # ------------------------------------------------------------------
    # Embedding 生成
    # ------------------------------------------------------------------

    def embed(self, texts: List[str]) -> List[List[float]]:
        """把文本列表转成向量矩阵。失败或不可用时返回随机向量占位（不影响后续流程）。"""
        if settings.embedding_backend == "mock":
            return [[random.uniform(-1, 1) for _ in range(self.embedding_dim)] for _ in texts]
        if self._embedding_model is None:
            logger.warning("embedding 模型不可用，返回空向量占位")
            return [[0.0] * self.embedding_dim for _ in texts]
        try:
            import numpy as np  # type: ignore
            embeddings = self._embedding_model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
            # numpy → list[list[float]]
            if isinstance(embeddings, np.ndarray):
                return embeddings.tolist()
            return [e.tolist() for e in embeddings]
        except Exception as exc:
            logger.warning("embedding 生成失败: %s", exc)
            return [[0.0] * self.embedding_dim for _ in texts]

    # ------------------------------------------------------------------
    # Upsert
    # ------------------------------------------------------------------

    @_with_retry("upsert")
    def upsert(self, points: List[PointStruct]) -> None:
        if self.client is None or not points:
            return
        self.client.upsert(collection_name=settings.qdrant_collection, points=points)

    # ------------------------------------------------------------------
    # Search（向量检索核心）
    # ------------------------------------------------------------------

    @_with_retry("query_points")
    def search(
        self,
        vector: List[float],
        top_k: int = 5,
        tenant_id: str | None = None,
        doc_id: int | None = None,
    ) -> List[dict]:
        """向量相似度检索（Qdrant 新 API: query_points）。

        返回格式（与 ILIKE 结果统一）：
          [{"id": int/str, "doc_id": int, "page_no": int, "section": str,
            "content": str, "score": float, "source": "qdrant"}, ...]
        任何异常 → 返回空列表（让上层自动走到 ILIKE 兜底）。
        """
        if self.client is None or not vector:
            return []

        must_conditions: List[FieldCondition] = []
        if tenant_id:
            must_conditions.append(
                FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id))
            )
        if doc_id is not None:
            must_conditions.append(
                FieldCondition(key="doc_id", match=MatchValue(value=doc_id))
            )
        query_filter = Filter(must=must_conditions) if must_conditions else None

        response = self.client.query_points(
            collection_name=settings.qdrant_collection,
            query=vector,
            query_filter=query_filter,
            limit=top_k,
            with_payload=True,
        )

        results = []
        for hit in response.points:
            payload = hit.payload or {}
            results.append({
                "id": hit.id,
                "doc_id": payload.get("doc_id"),
                "page_no": payload.get("page_no", 1),
                "section": payload.get("section"),
                "content": payload.get("content", ""),
                "chunk_type": payload.get("chunk_type", "text"),
                "score": hit.score,
                "source": "qdrant",
            })
        return results

    # ------------------------------------------------------------------
    # 删除（供运维/清理用）
    # ------------------------------------------------------------------

    @_with_retry("delete_by_doc")
    def delete_by_doc(self, doc_id: int, tenant_id: str | None = None) -> int:
        """删除指定 doc_id 的所有向量，返回删除数量（Qdrant 返回的是 PointIdsSelector，
        这里简化用 filter 删除后返回近似 count）。"""
        if self.client is None:
            return 0
        must_conditions: List[FieldCondition] = [
            FieldCondition(key="doc_id", match=MatchValue(value=doc_id))
        ]
        if tenant_id:
            must_conditions.append(
                FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id))
            )
        from qdrant_client.http.models import FilterSelector
        filter_obj = Filter(must=must_conditions)
        # Qdrant delete 返回 OperationResult，operation_id 数字表示删除条数近似值
        self.client.delete(
            collection_name=settings.qdrant_collection,
            points_selector=FilterSelector(filter=filter_obj),
        )
        logger.info("Qdrant delete doc_id=%s tenant=%s 完成", doc_id, tenant_id)
        return -1  # 真实 count Qdrant 不直接返回，返回 -1 表示"已删除、数量未知"


vector_store = VectorStore()
