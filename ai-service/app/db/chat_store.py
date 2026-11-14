"""对话会话持久化模块。

职责：
1. upsert_chat_session(external_id, tenant_id, user_id) —— 确保会话行存在
2. load_history_messages(external_id, tenant_id, limit) —— 拉取最近 N 轮 user/assistant 消息，用于多轮对话上下文
3. save_message(external_id, tenant_id, role, content, citations, session_internal_id) —— 写 user / assistant 消息
4. save_chat_event(...) —— 写 SSE 事件时间线
5. update_session_activity(external_id, tenant_id, title) —— 更新 last_active_at / title

幂等设计：
- 所有 DB 操作都有 try-except，失败只 log + warn，不抛给 graph 主链路
- 连接用 settings.postgres_dsn，短连接模式（用完即关）
"""
from __future__ import annotations

import logging
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 内部：短连接获取（用完 with 自动 close）
# ---------------------------------------------------------------------------

def _connect():
    import psycopg
    return psycopg.connect(settings.postgres_dsn, connect_timeout=5)


# ---------------------------------------------------------------------------
# 会话级
# ---------------------------------------------------------------------------

def upsert_chat_session(
    external_id: str,
    tenant_id: str,
    user_id: Optional[int] = None,
    title: Optional[str] = None,
) -> Optional[int]:
    """确保 chat_session 行存在，返回内部自增 id（给 message.session_id 用）。

    如果已有行 → 更新 last_active_at（和可选 title）
    如果不存在 → INSERT
    连接失败返回 None（不阻断主链路）。
    """
    if not external_id or not tenant_id:
        logger.warning("upsert_chat_session 缺参数: external_id=%r tenant_id=%r", external_id, tenant_id)
        return None
    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO chat_session (external_id, tenant_id, user_id, title, last_active_at)
                    VALUES (%s, %s, %s, %s, now())
                    ON CONFLICT (tenant_id, external_id) DO UPDATE
                        SET last_active_at = now(),
                            title = COALESCE(EXCLUDED.title, chat_session.title)
                    RETURNING id
                    """,
                    (external_id, tenant_id, user_id, title),
                )
                row = cur.fetchone()
                conn.commit()
                return row[0] if row else None
    except Exception as exc:
        logger.warning("chat_session upsert 失败 external_id=%s: %s", external_id, exc)
        return None


def update_session_title(external_id: str, tenant_id: str, title: str) -> None:
    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE chat_session SET title = %s, last_active_at = now() "
                    "WHERE external_id = %s AND tenant_id = %s",
                    (title, external_id, tenant_id),
                )
                conn.commit()
    except Exception as exc:
        logger.warning("chat_session title 更新失败: %s", exc)


def touch_session_activity(external_id: str, tenant_id: str) -> None:
    """纯心跳式 last_active_at 更新（很轻）。"""
    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE chat_session SET last_active_at = now() "
                    "WHERE external_id = %s AND tenant_id = %s",
                    (external_id, tenant_id),
                )
                conn.commit()
    except Exception as exc:
        logger.debug("session activity touch 失败: %s", exc)


# ---------------------------------------------------------------------------
# 历史加载（给多轮对话上下文用）
# ---------------------------------------------------------------------------

def load_history_messages(
    external_id: str,
    tenant_id: str,
    limit: int = 10,
) -> list[dict]:
    """拉取最近 N 轮 user/assistant 消息，按时间升序。

    返回格式：[{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
    用于拼 LangGraph answer 节点的 messages 上下文。
    """
    if not external_id or not tenant_id:
        return []
    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT role, content
                    FROM message
                    WHERE external_session_id = %s AND tenant_id = %s AND role IN ('user', 'assistant')
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (external_id, tenant_id, limit * 2),  # 每轮两条
                )
                rows = cur.fetchall()
        # DESC 取出来是倒序的，翻回来变成时间升序
        return [{"role": r[0], "content": r[1]} for r in reversed(rows)]
    except Exception as exc:
        logger.warning("历史消息加载失败 external_id=%s: %s", external_id, exc)
        return []


def get_session_messages(
    external_id: str,
    tenant_id: str,
    limit: int = 200,
) -> list[dict]:
    """拉取会话的完整消息流（时间升序），用于前端恢复历史对话。

    与 load_history_messages 的区别：返回 id / citations / created_at，
    不做 10 轮截断，供页面完整渲染。
    """
    if not external_id or not tenant_id:
        return []
    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, role, content, citations, created_at
                    FROM message
                    WHERE external_session_id = %s AND tenant_id = %s
                      AND role IN ('user', 'assistant')
                    ORDER BY created_at ASC, id ASC
                    LIMIT %s
                    """,
                    (external_id, tenant_id, limit),
                )
                rows = cur.fetchall()
        return [
            {
                "id": r[0],
                "role": r[1],
                "content": r[2],
                "citations": r[3] or [],
                "created_at": r[4].isoformat() if r[4] else None,
            }
            for r in rows
        ]
    except Exception as exc:
        logger.warning("会话消息查询失败 external_id=%s: %s", external_id, exc)
        return []


def list_sessions(
    tenant_id: str,
    keyword: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """按租户列出历史会话，按最后活跃时间倒序。

    - keyword：匹配会话标题或任一消息内容（ILIKE，忽略大小写）
    - start / end：last_active_at 时间范围（ISO 字符串）
    """
    if not tenant_id:
        return []
    conds = ["s.tenant_id = %s"]
    params: list = [tenant_id]

    if keyword:
        like = f"%{keyword.strip()}%"
        conds.append(
            "(COALESCE(s.title, '') ILIKE %s OR EXISTS ("
            "  SELECT 1 FROM message m WHERE m.external_session_id = s.external_id"
            "  AND m.tenant_id = s.tenant_id AND m.content ILIKE %s))"
        )
        params.extend([like, like])
    if start:
        conds.append("s.last_active_at >= %s")
        params.append(start)
    if end:
        conds.append("s.last_active_at <= %s")
        params.append(end)

    sql = f"""
        SELECT s.external_id,
               COALESCE(s.title, '') AS title,
               s.last_active_at,
               (SELECT count(*) FROM message m
                 WHERE m.external_session_id = s.external_id AND m.tenant_id = s.tenant_id) AS message_count,
               (SELECT m.content FROM message m
                 WHERE m.external_session_id = s.external_id AND m.tenant_id = s.tenant_id
                   AND m.role = 'user'
                 ORDER BY m.created_at ASC LIMIT 1) AS first_question
        FROM chat_session s
        WHERE {' AND '.join(conds)}
        ORDER BY s.last_active_at DESC NULLS LAST
        LIMIT %s OFFSET %s
    """
    params.extend([limit, offset])

    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, tuple(params))
                rows = cur.fetchall()
        return [
            {
                "session_id": r[0],
                "title": r[1] or (r[4] or "")[:40] or "新会话",
                "last_active_at": r[2].isoformat() if r[2] else None,
                "message_count": r[3],
                "preview": (r[4] or "")[:80],
            }
            for r in rows
        ]
    except Exception as exc:
        logger.warning("会话列表查询失败 tenant=%s: %s", tenant_id, exc)
        return []


# ---------------------------------------------------------------------------
# 消息级（每轮 user 输入 / assistant 输出各一条）
# ---------------------------------------------------------------------------

def save_message(
    external_id: str,
    tenant_id: str,
    role: str,                    # 'user' | 'assistant'
    content: str,
    citations: Optional[list[dict]] = None,
    session_internal_id: Optional[int] = None,
) -> None:
    if not external_id or not tenant_id or not role:
        return
    try:
        import json as _json
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO message (tenant_id, session_id, external_session_id, role, content, citations)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        tenant_id,
                        session_internal_id,
                        external_id,
                        role,
                        content,
                        _json.dumps(citations, ensure_ascii=False) if citations else None,
                    ),
                )
                conn.commit()
    except Exception as exc:
        logger.warning("message 写入失败 role=%s external_id=%s: %s", role, external_id, exc)


# ---------------------------------------------------------------------------
# 事件级（SSE 时间线逐条落库）
# ---------------------------------------------------------------------------

def save_chat_event(
    external_id: str,
    tenant_id: str,
    message_round: int,
    event_name: str,
    event_data: Optional[dict] = None,
    is_token: bool = False,
    token_content: Optional[str] = None,
    trace_id: Optional[str] = None,
) -> None:
    """每条 SSE 事件落库。token 事件只存累计文本，event_data 可以为 None 节省空间。

    调用频率高（每个 token 事件一次），所以这里做 best-effort，
    失败只 debug warn，不影响主链路。
    """
    if not external_id or not tenant_id:
        return
    try:
        import json as _json
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO chat_event (
                        tenant_id, external_session_id, message_round, trace_id,
                        event_name, event_data, is_token, token_content
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        tenant_id,
                        external_id,
                        message_round,
                        trace_id,
                        event_name,
                        _json.dumps(event_data, ensure_ascii=False) if event_data else None,
                        is_token,
                        token_content if is_token else None,
                    ),
                )
                conn.commit()
    except Exception as exc:
        logger.debug("chat_event 写入失败 %s external_id=%s: %s", event_name, external_id, exc)
