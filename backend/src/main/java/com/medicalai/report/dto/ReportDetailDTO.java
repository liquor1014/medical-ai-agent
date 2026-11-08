package com.medicalai.report.dto;

import com.fasterxml.jackson.annotation.JsonIgnore;
import lombok.Data;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

/**
 * 报表详情（含表格数据）
 */
@Data
public class ReportDetailDTO {

    private Long id;
    private String question;
    private String sql;
    private String status;
    private String chartType;
    private LocalDateTime createdAt;

    private List<String> columns = List.of();
    private List<Map<String, Object>> rows = List.of();

    /** 原始 jsonb 文本，仅用于解析，不返回给前端 */
    @JsonIgnore
    private String resultJson;
}
