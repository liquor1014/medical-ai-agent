"""模型提供者配置持久化（model_provider_config）。

职责：
1. ensure_table() —— 幂等建表，迁移脚本未执行时也能自愈
2. list_configs() —— 启动时加载全部持久化配置，覆盖环境变量默认值
3. upsert_config(...) —— 新增/编辑/启停后实时落库

设计：
- 短连接模式（用完即关），与 chat_store 保持一致
- 仅存储，不做业务校验；校验与内存态更新在 routers/models.py 与 ModelRouter 中完成
"""
from __future__ import annotations

import logging
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

_COLUMNS = "name, model, base_url, api_key, enabled, source"


def _connect():
    import psycopg
    return psycopg.connect(settings.postgres_dsn, connect_timeout=5)


def ensure_table() -> None:
    """幂等建表，避免未执行 006 迁移时功能不可用。"""
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS model_provider_config (
                name        VARCHAR(64)  PRIMARY KEY,
                model       VARCHAR(128) NOT NULL,
                base_url    VARCHAR(256) NOT NULL,
                api_key     TEXT         NOT NULL DEFAULT '',
                enabled     BOOLEAN      NOT NULL DEFAULT TRUE,
                source      VARCHAR(16)  NOT NULL DEFAULT 'custom',
                created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
                updated_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
            )
            """
        )
        conn.commit()


def _row_to_dict(row: tuple) -> dict:
    return {
        "name": row[0],
        "model": row[1],
        "base_url": row[2],
        "api_key": row[3] or "",
        "enabled": bool(row[4]),
        "source": row[5] or "custom",
    }


def list_configs() -> list[dict]:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT {_COLUMNS} FROM model_provider_config ORDER BY created_at, name"
            )
            rows = cur.fetchall()
    return [_row_to_dict(row) for row in rows]


def get_config(name: str) -> Optional[dict]:
    if not name:
        return None
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT {_COLUMNS} FROM model_provider_config WHERE name = %s",
                (name,),
            )
            row = cur.fetchone()
    return _row_to_dict(row) if row else None


def upsert_config(
    name: str,
    model: str,
    base_url: str,
    api_key: str = "",
    enabled: bool = True,
    source: str = "custom",
) -> dict:
    """写入或更新配置，返回落库后的完整记录。"""
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO model_provider_config (name, model, base_url, api_key, enabled, source)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (name) DO UPDATE SET
                    model = EXCLUDED.model,
                    base_url = EXCLUDED.base_url,
                    api_key = EXCLUDED.api_key,
                    enabled = EXCLUDED.enabled,
                    source = EXCLUDED.source,
                    updated_at = now()
                RETURNING {_COLUMNS}
                """,
                (name, model, base_url, api_key, bool(enabled), source),
            )
            row = cur.fetchone()
        conn.commit()
    logger.info("模型提供者配置已落库: name=%s enabled=%s", name, enabled)
    return _row_to_dict(row)
