package com.medicalai.report.dto;

import lombok.Data;

import java.time.LocalDateTime;

/**
 * 报表列表项
 */
@Data
public class ReportSummaryDTO {

    private Long id;
    private String question;
    private String status;
    private String chartType;
    private int rowCount;
    private LocalDateTime createdAt;
}
