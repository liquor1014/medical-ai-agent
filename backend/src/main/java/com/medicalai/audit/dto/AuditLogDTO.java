package com.medicalai.audit.dto;

import lombok.Data;

import java.time.LocalDateTime;

/**
 * 审计日志记录
 */
@Data
public class AuditLogDTO {

    private Long id;
    private String tenantId;
    private Long userId;
    private String action;
    private String sqlHash;
    private String result;
    private LocalDateTime createdAt;
}
