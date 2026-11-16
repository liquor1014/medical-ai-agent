package com.medicalai.common;

import lombok.RequiredArgsConstructor;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.util.HashSet;
import java.util.List;
import java.util.Set;

/**
 * 租户角色-权限映射 Repository
 */
@Repository
@RequiredArgsConstructor
public class TenantPermissionRepository {

    private final JdbcTemplate jdbc;

    /**
     * 查询指定租户 + 角色拥有的全部权限
     */
    public Set<String> findPermissions(String tenantId, String role) {
        List<String> list = jdbc.queryForList(
                "SELECT permission FROM tenant_permission WHERE tenant_id = ? AND role = ?",
                String.class, tenantId, role);
        return new HashSet<>(list);
    }

    /**
     * 判断指定租户 + 角色是否拥有某权限
     */
    public boolean hasPermission(String tenantId, String role, String permission) {
        Integer count = jdbc.queryForObject(
                "SELECT COUNT(*) FROM tenant_permission WHERE tenant_id = ? AND role = ? AND permission = ?",
                Integer.class, tenantId, role, permission);
        return count != null && count > 0;
    }

    /**
     * 为新角色在所有租户下写入默认业务权限（business:*），确保新角色可被分配后正常使用
     */
    public void insertDefaultBusinessPermissions(String role) {
        jdbc.update(
                "INSERT INTO tenant_permission (tenant_id, role, permission) " +
                "SELECT t.id, ?, p.permission FROM tenant t " +
                "CROSS JOIN (VALUES ('business:files'),('business:chat'),('business:reports')," +
                "('business:models'),('business:eval')) AS p(permission) " +
                "ON CONFLICT (tenant_id, role, permission) DO NOTHING",
                role);
    }

    /**
     * 删除指定角色在所有租户下的权限映射
     */
    public void deleteByRole(String role) {
        jdbc.update("DELETE FROM tenant_permission WHERE role = ?", role);
    }
}
