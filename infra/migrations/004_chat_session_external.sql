-- ============================================================================
-- 004: chat_session 扩展 + chat_event 表（会话持久化与多轮对话）
-- 幂等：所有 DDL 都带 IF NOT EXISTS / IF EXISTS 保护
-- ============================================================================

-- 1) chat_session 增加 external_id 存储前端传来的 UUID（session_id）
ALTER TABLE chat_session ADD COLUMN IF NOT EXISTS external_id VARCHAR(64);

-- 同一个 external_id 不应该出现多行（前端每次"新会话"生成一个新 UUID）
CREATE UNIQUE INDEX IF NOT EXISTS idx_chat_session_external
    ON chat_session (tenant_id, external_id);

-- 2) chat_session 增加最后活跃时间，便于按活跃度排序
ALTER TABLE chat_session ADD COLUMN IF NOT EXISTS last_active_at TIMESTAMPTZ NOT NULL DEFAULT now();

-- 3) message 表增加 external_session_id 冗余列，便于纯前端 UUID 查询（不 JOIN 也能用）
ALTER TABLE message ADD COLUMN IF NOT EXISTS external_session_id VARCHAR(64);
CREATE INDEX IF NOT EXISTS idx_message_external_session
    ON message (tenant_id, external_session_id, created_at);

-- 4) chat_event：每轮对话的 SSE 事件时间线
--    用来完整复盘：前端发了什么、AI 经历了哪些节点、最终产出了什么
CREATE TABLE IF NOT EXISTS chat_event (
    id                 BIGSERIAL PRIMARY KEY,
    tenant_id          VARCHAR(64)  NOT NULL,
    external_session_id VARCHAR(64) NOT NULL,     -- 前端 UUID
    message_round      INT          NOT NULL,    -- 第几轮对话（从 1 开始）
    trace_id           VARCHAR(64),
    event_name         VARCHAR(32)  NOT NULL,    -- start/intent/retrieval/token/sql/result/review/done/error...
    event_data         JSONB,                    -- 事件 payload（不含大段 token）
    is_token           BOOLEAN      NOT NULL DEFAULT FALSE,  -- 是否为 token 增量（单独标记，避免占满 event_data）
    token_content      TEXT,                     -- token 事件的实际文本（累计全文）
    created_at         TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chat_event_session_round
    ON chat_event (tenant_id, external_session_id, message_round, created_at);
CREATE INDEX IF NOT EXISTS idx_chat_event_trace
    ON chat_event (trace_id);
