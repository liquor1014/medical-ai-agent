-- 模型提供者配置持久化：支持页面新增 / 编辑 / 启停
-- 说明：
--   1. 一行代表一个提供者的完整配置，name 作为路由标识（唯一）
--   2. source 区分来源：env = 覆盖环境变量默认提供者，custom = 页面新增
--   3. api_key 在接口返回时统一脱敏，页面编辑留空表示保持原值
-- 幂等，可在已初始化的库上直接执行

CREATE TABLE IF NOT EXISTS model_provider_config (
    name        VARCHAR(64)  PRIMARY KEY,
    model       VARCHAR(128) NOT NULL,
    base_url    VARCHAR(256) NOT NULL,
    api_key     TEXT         NOT NULL DEFAULT '',
    enabled     BOOLEAN      NOT NULL DEFAULT TRUE,
    source      VARCHAR(16)  NOT NULL DEFAULT 'custom',
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_model_provider_config_enabled
    ON model_provider_config (enabled);
