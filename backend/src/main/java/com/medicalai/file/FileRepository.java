package com.medicalai.file;

import com.medicalai.common.TenantContext;
import com.medicalai.file.entity.Document;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.jdbc.support.GeneratedKeyHolder;
import org.springframework.jdbc.support.KeyHolder;
import org.springframework.stereotype.Repository;

import java.sql.PreparedStatement;
import java.sql.Statement;
import java.util.List;

/**
 * 文档 Repository（基于 JdbcTemplate）
 */
@Slf4j
@Repository
@RequiredArgsConstructor
public class FileRepository {

    private final JdbcTemplate jdbc;

    private final RowMapper<Document> rowMapper = (rs, rowNum) -> {
        Document d = new Document();
        d.setId(rs.getLong("id"));
        d.setTenantId(rs.getString("tenant_id"));
        d.setFileName(rs.getString("file_name"));
        d.setObjectKey(rs.getString("object_key"));
        d.setDocType(rs.getString("doc_type"));
        d.setStatus(rs.getString("status"));
        d.setPageCount(rs.getInt("page_count"));
        d.setChunkCount(rs.getInt("chunk_count"));
        d.setCreatedAt(rs.getTimestamp("created_at").toLocalDateTime());
        return d;
    };

    /**
     * 插入文档记录，返回自增 ID
     */
    public Long insert(Document doc) {
        String sql = "INSERT INTO document (tenant_id, file_name, object_key, doc_type, status) VALUES (?, ?, ?, ?, 'pending')";
        KeyHolder keyHolder = new GeneratedKeyHolder();
        jdbc.update(con -> {
            PreparedStatement ps = con.prepareStatement(sql, new String[]{"id"});
            ps.setString(1, doc.getTenantId());
            ps.setString(2, doc.getFileName());
            ps.setString(3, doc.getObjectKey());
            ps.setString(4, doc.getDocType());
            return ps;
        }, keyHolder);
        Number key = keyHolder.getKey();
        if (key == null) {
            // PostgreSQL 可能返回多列，取第一列
            key = (Number) keyHolder.getKeys().get("id");
        }
        return key.longValue();
    }

    /**
     * 更新解析状态
     */
    public void updateParseResult(Long id, String status, int pageCount, int chunkCount) {
        String sql = "UPDATE document SET status = ?, page_count = ?, chunk_count = ? WHERE id = ? AND tenant_id = ?";
        jdbc.update(sql, status, pageCount, chunkCount, id, TenantContext.getTenantId());
    }

    /**
     * 按租户查询文档列表
     */
    public List<Document> listByTenant(String tenantId) {
        String sql = "SELECT * FROM document WHERE tenant_id = ? ORDER BY created_at DESC";
        return jdbc.query(sql, rowMapper, tenantId);
    }

    /**
     * 按 ID 查询（找不到返回 null）
     */
    public Document findById(Long id, String tenantId) {
        String sql = "SELECT * FROM document WHERE id = ? AND tenant_id = ?";
        var list = jdbc.query(sql, rowMapper, id, tenantId);
        return list.isEmpty() ? null : list.get(0);
    }

    /**
     * 删除文档记录
     */
    public int deleteById(Long id, String tenantId) {
        String sql = "DELETE FROM document WHERE id = ? AND tenant_id = ?";
        return jdbc.update(sql, id, tenantId);
    }
}
