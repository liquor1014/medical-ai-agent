package com.medicalai.common;

import lombok.RequiredArgsConstructor;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

import java.util.List;

/**
 * 用户 Repository（基于 app_user 表）
 */
@Repository
@RequiredArgsConstructor
public class UserRepository {

    private final JdbcTemplate jdbc;

    private final RowMapper<UserAccount> rowMapper = (rs, rowNum) -> {
        UserAccount u = new UserAccount();
        u.setId(rs.getLong("id"));
        u.setTenantId(rs.getString("tenant_id"));
        u.setUsername(rs.getString("username"));
        u.setPasswordHash(rs.getString("password_hash"));
        u.setDisplayName(rs.getString("display_name"));
        u.setRole(rs.getString("role"));
        u.setStatus(rs.getString("status"));
        return u;
    };

    /**
     * 按租户 + 用户名查询（找不到返回 null）
     */
    public UserAccount findByTenantAndUsername(String tenantId, String username) {
        String sql = "SELECT * FROM app_user WHERE tenant_id = ? AND username = ?";
        List<UserAccount> list = jdbc.query(sql, rowMapper, tenantId, username);
        return list.isEmpty() ? null : list.get(0);
    }

    /**
     * 新增用户
     */
    public void insert(UserAccount user) {
        String sql = "INSERT INTO app_user (tenant_id, username, password_hash, display_name, role, status) VALUES (?, ?, ?, ?, ?, ?)";
        jdbc.update(sql, user.getTenantId(), user.getUsername(), user.getPasswordHash(),
                user.getDisplayName(), user.getRole(), user.getStatus());
    }
}
