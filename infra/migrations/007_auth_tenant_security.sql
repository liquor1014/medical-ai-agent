-- ============================================================================
-- 007: 租户管理 + 认证安全增强
--   1) tenant 表：替代代码中硬编码的租户列表，支持后台动态维护
--   2) app_user 扩展：邮箱（找回密码）、登录失败计数、锁定截止时间、最后登录时间
-- 幂等，可在已初始化的库上直接执行
-- ============================================================================

-- 1) 租户表
CREATE TABLE IF NOT EXISTS tenant (
    id          VARCHAR(64)  PRIMARY KEY,
    name        VARCHAR(128) NOT NULL,
    description VARCHAR(255),
    status      VARCHAR(16)  NOT NULL DEFAULT 'active',
    sort_order  INT          NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tenant_status ON tenant (status, sort_order);

-- 2) 内置租户（与历史前端选项保持一致）
INSERT INTO tenant (id, name, description, status, sort_order) VALUES
    ('hospital-demo', '演示院区', '默认演示租户', 'active', 0),
    ('hospital-a', 'A 院区', '示例租户 A', 'active', 10),
    ('hospital-b', 'B 院区', '示例租户 B', 'active', 20)
ON CONFLICT (id) DO NOTHING;

-- 3) 用户表扩展
ALTER TABLE app_user ADD COLUMN IF NOT EXISTS email VARCHAR(128);
ALTER TABLE app_user ADD COLUMN IF NOT EXISTS failed_attempts INT NOT NULL DEFAULT 0;
ALTER TABLE app_user ADD COLUMN IF NOT EXISTS locked_until TIMESTAMPTZ;
ALTER TABLE app_user ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMPTZ;
ALTER TABLE app_user ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

CREATE INDEX IF NOT EXISTS idx_app_user_email ON app_user (tenant_id, lower(email));

-- 4) 演示账号补充邮箱，便于直接体验找回密码流程（仅当邮箱为空时补齐）
UPDATE app_user
SET email = 'admin@demo.local'
WHERE tenant_id = 'hospital-demo' AND username = 'admin' AND (email IS NULL OR email = '');

UPDATE app_user
SET email = 'doctor@demo.local'
WHERE tenant_id = 'hospital-demo' AND username = 'doctor' AND (email IS NULL OR email = '');
