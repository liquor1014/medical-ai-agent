-- Day 8：用户登录改造（数据库用户 + BCrypt 密码）
-- 幂等，可在已初始化的库上直接执行

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS app_user (
    id            BIGSERIAL PRIMARY KEY,
    tenant_id     VARCHAR(64)  NOT NULL,
    username      VARCHAR(64)  NOT NULL,
    password_hash VARCHAR(128) NOT NULL,
    display_name  VARCHAR(128),
    role          VARCHAR(32)  NOT NULL DEFAULT 'doctor',
    status        VARCHAR(16)  NOT NULL DEFAULT 'active',
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, username)
);

CREATE INDEX IF NOT EXISTS idx_app_user_tenant ON app_user (tenant_id, username);

-- 内置演示账号（密码使用 BCrypt，与 Java 端 BCryptPasswordEncoder 兼容）
INSERT INTO app_user (tenant_id, username, password_hash, display_name, role)
VALUES ('hospital-demo', 'admin', crypt('admin123', gen_salt('bf', 10)), '系统管理员', 'admin')
ON CONFLICT (tenant_id, username) DO NOTHING;

INSERT INTO app_user (tenant_id, username, password_hash, display_name, role)
VALUES ('hospital-demo', 'doctor', crypt('doctor123', gen_salt('bf', 10)), '演示医生', 'doctor')
ON CONFLICT (tenant_id, username) DO NOTHING;
