"""Qdrant 向量存储封装。embedding 模型不可用时自动降级为不写入。"""
from __future__ import annotations

import logging
from typing import List, Optional

from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, PointStruct, VectorParams

from app.config import settings

logger = logging.getLogger(__name__)


class VectorStore:
    def __init__(self) -> None:
        self.client: Optional[QdrantClient] = None
        self.embedding_dim = 0
        self._init_client()

    def _init_client(self) -> None:
        try:
            self.client = QdrantClient(url=settings.qdrant_url)
            # 尝试探测 collection
            collections = self.client.get_collections().collections
            names = [c.name for c in collections]
            if settings.qdrant_collection not in names:
                logger.info("Qdrant collection %s 不存在，稍后创建", settings.qdrant_collection)
        except Exception as e:
            logger.warning("Qdrant 连接失败: %s", e)
            self.client = None

    @property
    def available(self) -> bool:
        return self.client is not None and self.embedding_dim > 0

    def ensure_collection(self, dim: int) -> None:
        if not self.client:
            return
        self.embedding_dim = dim
        collections = [c.name for c in self.client.get_collections().collections]
        if settings.qdrant_collection not in collections:
            self.client.create_collection(
                collection_name=settings.qdrant_collection,
                vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
            )
            logger.info("Qdrant collection %s 已创建 (dim=%d)", settings.qdrant_collection, dim)

    def upsert(self, points: List[PointStruct]) -> None:
        if not self.available or not points:
            return
        self.client.upsert(collection_name=settings.qdrant_collection, points=points)


vector_store = VectorStore()
