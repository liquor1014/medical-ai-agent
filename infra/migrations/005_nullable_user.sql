-- ============================================================================
-- 005: chat_session.user_id 允许 NULL
-- 原因：ai-service 层拿到的是 tenant_id + username，拿不到 app_user 自增 id；
--      真正的 user_id 关联可在 Java 网关层补写（后续扩展），ai-service 只负责会话落库
-- ============================================================================
ALTER TABLE chat_session ALTER COLUMN user_id DROP NOT NULL;

-- message.session_id 也允许 NULL（新会话时还不知道 internal_id）
ALTER TABLE message ALTER COLUMN session_id DROP NOT NULL;
