-- ============================================================================
-- 009: superAdmin 账号硬编码 + 角色配置表 + system:role 权限
--   1) 系统超级管理员账号统一为 superAdmin（原 admin 重命名）
--   2) 新增 role 表：角色元数据（code/name/description/status/is_builtin）
--   3) 种子内置角色 super_admin / tenant_admin / doctor
--   4) 为 super_admin 追加 system:role 权限（角色配置管理）
-- 幂等，可重复执行
-- ============================================================================

-- 1) 系统超级管理员账号统一为 superAdmin
UPDATE app_user SET username = 'superAdmin' WHERE username = 'admin';
UPDATE user_tenant SET role = 'super_admin'
WHERE user_id = (SELECT id FROM app_user WHERE username = 'superAdmin')
  AND role <> 'super_admin';

-- 2) 角色配置表
CREATE TABLE IF NOT EXISTS role (
    code        VARCHAR(32)  NOT NULL PRIMARY KEY,
    name        VARCHAR(64)  NOT NULL,
    description VARCHAR(255),
    status      VARCHAR(16)  NOT NULL DEFAULT 'enabled',
    is_builtin  BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- 3) 种子内置角色
INSERT INTO role (code, name, description, status, is_builtin) VALUES
    ('super_admin',  '系统超级管理员', '全平台最高权限，硬编码账号',        'enabled', TRUE),
    ('tenant_admin', '租户管理员',     '租户内用户与审计管理',             'enabled', TRUE),
    ('doctor',       '医生',           '业务功能访问',                     'enabled', TRUE)
ON CONFLICT (code) DO NOTHING;

-- 4) 为所有租户的 super_admin 追加 system:role 权限
INSERT INTO tenant_permission (tenant_id, role, permission)
SELECT id, 'super_admin', 'system:role' FROM tenant
ON CONFLICT (tenant_id, role, permission) DO NOTHING;
