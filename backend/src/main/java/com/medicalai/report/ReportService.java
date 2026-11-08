package com.medicalai.report;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.medicalai.common.BusinessException;
import com.medicalai.common.TenantContext;
import com.medicalai.report.dto.ReportDetailDTO;
import com.medicalai.report.dto.ReportSummaryDTO;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * 报表业务逻辑
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ReportService {

    private static final int LIST_LIMIT = 50;

    private final ReportRepository reportRepository;
    private final ObjectMapper objectMapper;

    /**
     * 当前租户的报表列表
     */
    public List<ReportSummaryDTO> list() {
        return reportRepository.listByTenant(TenantContext.getTenantId(), LIST_LIMIT);
    }

    /**
     * 报表详情（含列与数据行）
     */
    public ReportDetailDTO detail(Long id) {
        ReportDetailDTO dto = reportRepository.findById(id, TenantContext.getTenantId());
        if (dto == null) {
            throw new BusinessException(404, "报表不存在");
        }
        parseResult(dto);
        return dto;
    }

    /**
     * 导出 CSV（UTF-8 BOM，便于 Excel 直接打开）
     */
    public byte[] exportCsv(Long id) {
        ReportDetailDTO dto = detail(id);
        StringBuilder sb = new StringBuilder("\uFEFF");
        sb.append(csvLine(dto.getColumns()));
        for (Map<String, Object> row : dto.getRows()) {
            List<String> values = new ArrayList<>();
            for (String col : dto.getColumns()) {
                values.add(row.get(col) == null ? "" : String.valueOf(row.get(col)));
            }
            sb.append(csvLine(values));
        }
        return sb.toString().getBytes(StandardCharsets.UTF_8);
    }

    private void parseResult(ReportDetailDTO dto) {
        if (dto.getResultJson() == null || dto.getResultJson().isBlank()) {
            return;
        }
        try {
            JsonNode root = objectMapper.readTree(dto.getResultJson());
            List<String> columns = objectMapper.convertValue(
                    root.path("columns"), new TypeReference<List<String>>() {});
            List<Map<String, Object>> rows = objectMapper.convertValue(
                    root.path("rows"), new TypeReference<List<Map<String, Object>>>() {});
            dto.setColumns(columns == null ? List.of() : columns);
            dto.setRows(rows == null ? List.of() : rows);
        } catch (Exception e) {
            log.warn("报表结果解析失败: id={}", dto.getId(), e);
        }
    }

    private String csvLine(List<String> values) {
        List<String> escaped = new ArrayList<>(values.size());
        for (String v : values) {
            escaped.add(escapeCsv(v));
        }
        return String.join(",", escaped) + "\r\n";
    }

    private String escapeCsv(String value) {
        if (value == null) {
            return "";
        }
        if (value.contains(",") || value.contains("\"") || value.contains("\n") || value.contains("\r")) {
            return "\"" + value.replace("\"", "\"\"") + "\"";
        }
        return value;
    }
}
