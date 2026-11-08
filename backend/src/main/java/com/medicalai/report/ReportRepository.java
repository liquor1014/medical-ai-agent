package com.medicalai.report;

import com.medicalai.report.dto.ReportDetailDTO;
import com.medicalai.report.dto.ReportSummaryDTO;
import lombok.RequiredArgsConstructor;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.util.List;

/**
 * 报表 Repository（基于 report_query 表，按租户隔离）
 */
@Repository
@RequiredArgsConstructor
public class ReportRepository {

    private final JdbcTemplate jdbc;

    /**
     * 按租户查询报表列表
     */
    public List<ReportSummaryDTO> listByTenant(String tenantId, int limit) {
        String sql = """
                SELECT id, question, status, chart_type, created_at,
                       COALESCE(jsonb_array_length(result -> 'rows'), 0) AS row_count
                FROM report_query
                WHERE tenant_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """;
        return jdbc.query(sql, (rs, rowNum) -> {
            ReportSummaryDTO dto = new ReportSummaryDTO();
            dto.setId(rs.getLong("id"));
            dto.setQuestion(rs.getString("question"));
            dto.setStatus(rs.getString("status"));
            dto.setChartType(rs.getString("chart_type"));
            dto.setRowCount(rs.getInt("row_count"));
            dto.setCreatedAt(rs.getTimestamp("created_at").toLocalDateTime());
            return dto;
        }, tenantId, limit);
    }

    /**
     * 按 ID 查询报表详情（找不到返回 null）
     */
    public ReportDetailDTO findById(Long id, String tenantId) {
        String sql = """
                SELECT id, question, sql, status, chart_type, created_at, result::text AS result_json
                FROM report_query
                WHERE id = ? AND tenant_id = ?
                """;
        var list = jdbc.query(sql, (rs, rowNum) -> {
            ReportDetailDTO dto = new ReportDetailDTO();
            dto.setId(rs.getLong("id"));
            dto.setQuestion(rs.getString("question"));
            dto.setSql(rs.getString("sql"));
            dto.setStatus(rs.getString("status"));
            dto.setChartType(rs.getString("chart_type"));
            dto.setCreatedAt(rs.getTimestamp("created_at").toLocalDateTime());
            dto.setResultJson(rs.getString("result_json"));
            return dto;
        }, id, tenantId);
        return list.isEmpty() ? null : list.get(0);
    }
}
