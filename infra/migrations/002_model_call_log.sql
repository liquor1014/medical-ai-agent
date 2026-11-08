-- Day 7：扩展模型调用日志（多模型路由 / 降级 / 首字延迟）
-- 幂等，可在已初始化的库上直接执行

ALTER TABLE model_call_log
    ADD COLUMN IF NOT EXISTS provider       VARCHAR(64),
    ADD COLUMN IF NOT EXISTS trace_id       VARCHAR(64),
    ADD COLUMN IF NOT EXISTS status         VARCHAR(32) NOT NULL DEFAULT 'success',
    ADD COLUMN IF NOT EXISTS error          TEXT,
    ADD COLUMN IF NOT EXISTS first_token_ms INT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS fallback_from  VARCHAR(64);

CREATE INDEX IF NOT EXISTS idx_model_call_log_trace ON model_call_log (trace_id);
CREATE INDEX IF NOT EXISTS idx_model_call_log_status ON model_call_log (status, created_at);
