package com.medicalai.common;

import lombok.RequiredArgsConstructor;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

import java.time.OffsetDateTime;
import java.util.List;

/**
 * 租户 Repository（基于 tenant 表）
 */
@Repository
@RequiredArgsConstructor
public class TenantRepository {

    private final JdbcTemplate jdbc;

    private final RowMapper<Tenant> rowMapper = (rs, rowNum) -> {
        Tenant t = new Tenant();
        t.setId(rs.getString("id"));
        t.setName(rs.getString("name"));
        t.setDescription(rs.getString("description"));
        t.setStatus(rs.getString("status"));
        t.setSortOrder(rs.getInt("sort_order"));
        t.setUserCount(rs.getInt("user_count"));
        t.setCreatedAt(rs.getObject("created_at", OffsetDateTime.class));
        t.setUpdatedAt(rs.getObject("updated_at", OffsetDateTime.class));
        return t;
    };

    private static final String BASE_SQL = """
            SELECT t.id, t.name, t.description, t.status, t.sort_order, t.created_at, t.updated_at,
                   (SELECT COUNT(*) FROM app_user u WHERE u.tenant_id = t.id) AS user_count
            FROM tenant t
            """;

    /**
     * 查询租户列表；onlyActive=true 时仅返回启用租户（登录页使用）
     */
    public List<Tenant> findAll(boolean onlyActive) {
        String sql = BASE_SQL + (onlyActive ? " WHERE t.status = 'active'" : "") + " ORDER BY t.sort_order, t.id";
        return jdbc.query(sql, rowMapper);
    }

    public Tenant findById(String id) {
        List<Tenant> list = jdbc.query(BASE_SQL + " WHERE t.id = ?", rowMapper, id);
        return list.isEmpty() ? null : list.get(0);
    }

    public void insert(Tenant tenant) {
        jdbc.update("INSERT INTO tenant (id, name, description, status, sort_order) VALUES (?, ?, ?, ?, ?)",
                tenant.getId(), tenant.getName(), tenant.getDescription(),
                tenant.getStatus(), tenant.getSortOrder());
    }

    public void update(Tenant tenant) {
        jdbc.update("UPDATE tenant SET name = ?, description = ?, status = ?, sort_order = ?, updated_at = now() "
                        + "WHERE id = ?",
                tenant.getName(), tenant.getDescription(), tenant.getStatus(),
                tenant.getSortOrder(), tenant.getId());
    }

    public void delete(String id) {
        jdbc.update("DELETE FROM tenant WHERE id = ?", id);
    }

    public int countUsers(String tenantId) {
        Integer value = jdbc.queryForObject("SELECT COUNT(*) FROM app_user WHERE tenant_id = ?",
                Integer.class, tenantId);
        return value == null ? 0 : value;
    }
}
