-- ============================================================================
-- 008: 多租户用户绑定 + 角色权限体系
--   1) user_tenant：用户-租户多对多绑定，每个用户在每个租户下有独立角色
--   2) tenant_permission：租户内角色-权限映射表
--   3) 用户名改为全局唯一（支持同一用户名绑定多个租户）
--   4) 每个租户仅允许一个 tenant_admin（部分唯一索引）
-- 幂等，可在已初始化的库上直接执行
-- ============================================================================

-- 1) 用户名改为全局唯一
ALTER TABLE app_user DROP CONSTRAINT IF EXISTS app_user_tenant_id_username_key;
CREATE UNIQUE INDEX IF NOT EXISTS uk_app_user_username ON app_user (username);

-- 2) 用户-租户绑定表
CREATE TABLE IF NOT EXISTS user_tenant (
    user_id    BIGINT      NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    tenant_id  VARCHAR(64) NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    role       VARCHAR(32) NOT NULL DEFAULT 'doctor',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, tenant_id)
);

CREATE INDEX IF NOT EXISTS idx_user_tenant_tenant ON user_tenant (tenant_id, role);
CREATE INDEX IF NOT EXISTS idx_user_tenant_user ON user_tenant (user_id);

-- 每个租户仅允许一个租户管理员
DROP INDEX IF EXISTS uk_tenant_admin;
CREATE UNIQUE INDEX uk_tenant_admin ON user_tenant (tenant_id) WHERE role = 'tenant_admin';

-- 3) 角色-权限映射表
CREATE TABLE IF NOT EXISTS tenant_permission (
    tenant_id  VARCHAR(64) NOT NULL,
    role       VARCHAR(32) NOT NULL,
    permission VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, role, permission)
);

-- 4) 迁移历史数据：将 app_user 既有行转为 user_tenant 绑定
INSERT INTO user_tenant (user_id, tenant_id, role)
SELECT id, tenant_id, role FROM app_user
ON CONFLICT (user_id, tenant_id) DO NOTHING;

-- 系统管理员角色升级为 super_admin（全平台权限）
UPDATE app_user SET role = 'super_admin' WHERE username = 'admin' AND role <> 'super_admin';
UPDATE user_tenant SET role = 'super_admin'
WHERE user_id = (SELECT id FROM app_user WHERE username = 'admin')
  AND role <> 'super_admin';

-- 5) 为所有租户的三类角色写入默认权限
--    super_admin：全权限（运行时由代码直接放行，此处也写入以保持一致）
--    tenant_admin：租户内用户/角色管理、审计查看、业务访问
--    doctor：仅业务访问
INSERT INTO tenant_permission (tenant_id, role, permission)
SELECT t.id, r.role, p.permission
FROM tenant t
CROSS JOIN (VALUES ('super_admin'), ('tenant_admin'), ('doctor')) AS r(role)
CROSS JOIN (
    VALUES
        ('business:files'),
        ('business:chat'),
        ('business:reports'),
        ('business:models'),
        ('business:eval'),
        ('system:audit'),
        ('system:user'),
        ('system:tenant')
) AS p(permission)
WHERE (r.role = 'super_admin')
   OR (r.role = 'tenant_admin' AND p.permission IN ('business:files','business:chat','business:reports','business:models','business:eval','system:audit','system:user'))
   OR (r.role = 'doctor'      AND p.permission IN ('business:files','business:chat','business:reports','business:models','business:eval'))
ON CONFLICT (tenant_id, role, permission) DO NOTHING;
