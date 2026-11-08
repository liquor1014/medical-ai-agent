package com.medicalai.audit;

import com.medicalai.audit.dto.AuditLogDTO;
import lombok.RequiredArgsConstructor;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 审计日志 Repository（按租户隔离）
 */
@Repository
@RequiredArgsConstructor
public class AuditRepository {

    private final JdbcTemplate jdbc;

    public List<AuditLogDTO> findPage(String tenantId, String action, String result, int offset, int size) {
        List<Object> args = new ArrayList<>();
        StringBuilder sql = new StringBuilder("""
                SELECT id, tenant_id, user_id, action, sql_hash, result, created_at
                FROM audit_log
                WHERE tenant_id = ?
                """);
        args.add(tenantId);
        appendFilters(sql, args, action, result);
        sql.append(" ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?");
        args.add(size);
        args.add(offset);

        return jdbc.query(sql.toString(), (rs, rowNum) -> {
            AuditLogDTO dto = new AuditLogDTO();
            dto.setId(rs.getLong("id"));
            dto.setTenantId(rs.getString("tenant_id"));
            dto.setUserId(rs.getLong("user_id"));
            dto.setAction(rs.getString("action"));
            dto.setSqlHash(rs.getString("sql_hash"));
            dto.setResult(rs.getString("result"));
            dto.setCreatedAt(rs.getTimestamp("created_at").toLocalDateTime());
            return dto;
        }, args.toArray());
    }

    public long count(String tenantId, String action, String result) {
        List<Object> args = new ArrayList<>();
        StringBuilder sql = new StringBuilder("SELECT COUNT(*) FROM audit_log WHERE tenant_id = ?");
        args.add(tenantId);
        appendFilters(sql, args, action, result);
        Long value = jdbc.queryForObject(sql.toString(), Long.class, args.toArray());
        return value == null ? 0 : value;
    }

    public Map<String, Long> countsByResult(String tenantId) {
        String sql = """
                SELECT COALESCE(result, 'unknown') AS result, COUNT(*) AS cnt
                FROM audit_log
                WHERE tenant_id = ?
                GROUP BY COALESCE(result, 'unknown')
                """;
        return jdbc.query(sql, rs -> {
            Map<String, Long> counts = new LinkedHashMap<>();
            while (rs.next()) {
                counts.put(rs.getString("result"), rs.getLong("cnt"));
            }
            return counts;
        }, tenantId);
    }

    public long countLast24h(String tenantId) {
        String sql = """
                SELECT COUNT(*) FROM audit_log
                WHERE tenant_id = ? AND created_at >= now() - interval '24 hours'
                """;
        Long value = jdbc.queryForObject(sql, Long.class, tenantId);
        return value == null ? 0 : value;
    }

    public List<String> distinctActions(String tenantId) {
        return jdbc.queryForList(
                "SELECT DISTINCT action FROM audit_log WHERE tenant_id = ? ORDER BY action",
                String.class, tenantId);
    }

    private void appendFilters(StringBuilder sql, List<Object> args, String action, String result) {
        if (action != null && !action.isBlank()) {
            sql.append(" AND action = ?");
            args.add(action);
        }
        if (result != null && !result.isBlank()) {
            sql.append(" AND result = ?");
            args.add(result);
        }
    }
}
