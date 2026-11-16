package com.medicalai.common;

import lombok.RequiredArgsConstructor;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

import java.util.List;

/**
 * 用户-租户绑定 Repository
 */
@Repository
@RequiredArgsConstructor
public class UserTenantRepository {

    private final JdbcTemplate jdbc;

    private final RowMapper<UserTenant> rowMapper = (rs, rowNum) -> {
        UserTenant ut = new UserTenant();
        ut.setUserId(rs.getLong("user_id"));
        ut.setTenantId(rs.getString("tenant_id"));
        ut.setRole(rs.getString("role"));
        ut.setCreatedAt(rs.getObject("created_at", java.time.OffsetDateTime.class));
        return ut;
    };

    /**
     * 查询用户在指定租户下的绑定（不存在返回 null）
     */
    public UserTenant findBinding(Long userId, String tenantId) {
        List<UserTenant> list = jdbc.query(
                "SELECT * FROM user_tenant WHERE user_id = ? AND tenant_id = ?",
                rowMapper, userId, tenantId);
        return list.isEmpty() ? null : list.get(0);
    }

    /**
     * 查询用户绑定的所有租户
     */
    public List<UserTenant> findByUser(Long userId) {
        return jdbc.query("SELECT * FROM user_tenant WHERE user_id = ? ORDER BY tenant_id",
                rowMapper, userId);
    }

    /**
     * 查询指定租户下的所有用户绑定
     */
    public List<UserTenant> findByTenant(String tenantId) {
        return jdbc.query("SELECT * FROM user_tenant WHERE tenant_id = ? ORDER BY role, user_id",
                rowMapper, tenantId);
    }

    /**
     * 统计指定租户内某角色的用户数（用于租户管理员唯一性校验）
     */
    public int countByTenantAndRole(String tenantId, String role) {
        Integer value = jdbc.queryForObject(
                "SELECT COUNT(*) FROM user_tenant WHERE tenant_id = ? AND role = ?",
                Integer.class, tenantId, role);
        return value == null ? 0 : value;
    }

    /**
     * 统计全平台使用某角色的用户数（用于删除角色前的引用检查）
     */
    public int countByRole(String role) {
        Integer value = jdbc.queryForObject(
                "SELECT COUNT(*) FROM user_tenant WHERE role = ?",
                Integer.class, role);
        return value == null ? 0 : value;
    }

    /**
     * 新增绑定（重复会抛出 DuplicateKeyException）
     */
    public void insert(UserTenant binding) {
        try {
            jdbc.update("INSERT INTO user_tenant (user_id, tenant_id, role) VALUES (?, ?, ?)",
                    binding.getUserId(), binding.getTenantId(), binding.getRole());
        } catch (DuplicateKeyException e) {
            throw new BusinessException(409, "该用户已绑定此租户");
        }
    }

    /**
     * 更新用户在指定租户下的角色
     */
    public void updateRole(Long userId, String tenantId, String role) {
        int rows = jdbc.update("UPDATE user_tenant SET role = ? WHERE user_id = ? AND tenant_id = ?",
                role, userId, tenantId);
        if (rows == 0) {
            throw new BusinessException(404, "用户未绑定该租户");
        }
    }

    /**
     * 解除绑定
     */
    public void delete(Long userId, String tenantId) {
        jdbc.update("DELETE FROM user_tenant WHERE user_id = ? AND tenant_id = ?", userId, tenantId);
    }
}
