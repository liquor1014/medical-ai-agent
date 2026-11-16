package com.medicalai.common;

import lombok.RequiredArgsConstructor;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.jdbc.support.GeneratedKeyHolder;
import org.springframework.jdbc.support.KeyHolder;
import org.springframework.stereotype.Repository;

import java.sql.PreparedStatement;
import java.sql.Statement;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;

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
        u.setEmail(rs.getString("email"));
        u.setFailedAttempts(rs.getInt("failed_attempts"));
        u.setLockedUntil(rs.getObject("locked_until", OffsetDateTime.class));
        u.setLastLoginAt(rs.getObject("last_login_at", OffsetDateTime.class));
        return u;
    };

    /**
     * 按用户名全局查询（用户名全局唯一）
     */
    public UserAccount findByUsername(String username) {
        List<UserAccount> list = jdbc.query("SELECT * FROM app_user WHERE username = ?",
                rowMapper, username);
        return list.isEmpty() ? null : list.get(0);
    }

    /**
     * 按主键查询
     */
    public UserAccount findById(Long id) {
        List<UserAccount> list = jdbc.query("SELECT * FROM app_user WHERE id = ?",
                rowMapper, id);
        return list.isEmpty() ? null : list.get(0);
    }

    /**
     * 查询某租户下的全部用户及其在该租户中的角色（关联 user_tenant）
     */
    public List<java.util.Map<String, Object>> findUsersByTenant(String tenantId) {
        String sql = "SELECT u.id, u.username, u.display_name, u.email, u.status, "
                + "u.last_login_at, ut.role "
                + "FROM app_user u JOIN user_tenant ut ON ut.user_id = u.id "
                + "WHERE ut.tenant_id = ? ORDER BY ut.role, u.username";
        return jdbc.queryForList(sql, tenantId);
    }

    /**
     * 新增用户，返回生成的主键 ID
     */
    public long insert(UserAccount user) {
        String sql = "INSERT INTO app_user (tenant_id, username, password_hash, display_name, role, status, email) "
                + "VALUES (?, ?, ?, ?, ?, ?, ?)";
        KeyHolder keyHolder = new GeneratedKeyHolder();
        jdbc.update(connection -> {
            PreparedStatement ps = connection.prepareStatement(sql, Statement.RETURN_GENERATED_KEYS);
            ps.setString(1, user.getTenantId());
            ps.setString(2, user.getUsername());
            ps.setString(3, user.getPasswordHash());
            ps.setString(4, user.getDisplayName());
            ps.setString(5, user.getRole());
            ps.setString(6, user.getStatus());
            ps.setString(7, user.getEmail());
            return ps;
        }, keyHolder);
        List<Map<String, Object>> keys = keyHolder.getKeyList();
        if (keys.isEmpty()) {
            return -1;
        }
        Object id = keys.get(0).get("id");
        return id == null ? -1 : ((Number) id).longValue();
    }

    /**
     * 更新密码（注册 / 改密 / 重置共用）
     */
    public void updatePassword(String username, String passwordHash) {
        jdbc.update("UPDATE app_user SET password_hash = ?, updated_at = now() WHERE username = ?",
                passwordHash, username);
    }

    /**
     * 登录失败计数 +1，返回累计失败次数
     */
    public int incrementFailedAttempts(String username) {
        Integer value = jdbc.queryForObject(
                "UPDATE app_user SET failed_attempts = failed_attempts + 1, updated_at = now() "
                        + "WHERE username = ? RETURNING failed_attempts",
                Integer.class, username);
        return value == null ? 1 : value;
    }

    /**
     * 锁定账号到指定时间
     */
    public void lockAccount(String username, OffsetDateTime lockedUntil) {
        jdbc.update("UPDATE app_user SET locked_until = ?, updated_at = now() WHERE username = ?",
                lockedUntil, username);
    }

    /**
     * 清除过期锁定（保留失败计数由后续流程重置）
     */
    public void clearExpiredLock(String username) {
        jdbc.update("UPDATE app_user SET locked_until = NULL, failed_attempts = 0, updated_at = now() "
                + "WHERE username = ?", username);
    }

    /**
     * 登录成功 / 密码重置后清空失败计数与锁定状态
     */
    public void markLoginSuccess(String username) {
        jdbc.update("UPDATE app_user SET failed_attempts = 0, locked_until = NULL, last_login_at = now(), "
                + "updated_at = now() WHERE username = ?", username);
    }

    /**
     * 密码变更后清空失败计数与锁定状态（不更新最后登录时间）
     */
    public void clearLoginState(String username) {
        jdbc.update("UPDATE app_user SET failed_attempts = 0, locked_until = NULL, updated_at = now() "
                + "WHERE username = ?", username);
    }
}
