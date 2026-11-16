package com.medicalai.common;

import lombok.RequiredArgsConstructor;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

import java.util.List;

/**
 * 角色配置 Repository
 */
@Repository
@RequiredArgsConstructor
public class RoleRepository {

    private final JdbcTemplate jdbc;

    private final RowMapper<Role> rowMapper = (rs, rowNum) -> {
        Role r = new Role();
        r.setCode(rs.getString("code"));
        r.setName(rs.getString("name"));
        r.setDescription(rs.getString("description"));
        r.setStatus(rs.getString("status"));
        r.setIsBuiltin(rs.getBoolean("is_builtin"));
        r.setCreatedAt(rs.getObject("created_at", java.time.OffsetDateTime.class));
        r.setUpdatedAt(rs.getObject("updated_at", java.time.OffsetDateTime.class));
        return r;
    };

    public List<Role> findAll() {
        return jdbc.query("SELECT * FROM role ORDER BY is_builtin DESC, code", rowMapper);
    }

    public List<Role> findEnabled() {
        return jdbc.query("SELECT * FROM role WHERE status = 'enabled' ORDER BY is_builtin DESC, code", rowMapper);
    }

    public Role findByCode(String code) {
        List<Role> list = jdbc.query("SELECT * FROM role WHERE code = ?", rowMapper, code);
        return list.isEmpty() ? null : list.get(0);
    }

    public void insert(Role role) {
        try {
            jdbc.update(
                    "INSERT INTO role (code, name, description, status, is_builtin) VALUES (?, ?, ?, ?, ?)",
                    role.getCode(), role.getName(), role.getDescription(),
                    role.getStatus(), role.getIsBuiltin());
        } catch (DuplicateKeyException e) {
            throw new BusinessException(409, "角色编码已存在");
        }
    }

    public void update(Role role) {
        int rows = jdbc.update(
                "UPDATE role SET name = ?, description = ?, updated_at = now() WHERE code = ?",
                role.getName(), role.getDescription(), role.getCode());
        if (rows == 0) {
            throw new BusinessException(404, "角色不存在");
        }
    }

    public void updateStatus(String code, String status) {
        int rows = jdbc.update("UPDATE role SET status = ?, updated_at = now() WHERE code = ?", status, code);
        if (rows == 0) {
            throw new BusinessException(404, "角色不存在");
        }
    }

    public void delete(String code) {
        jdbc.update("DELETE FROM role WHERE code = ?", code);
    }
}
