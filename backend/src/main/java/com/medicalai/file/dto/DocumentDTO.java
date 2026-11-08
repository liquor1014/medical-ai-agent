package com.medicalai.file.dto;

import lombok.Data;

import java.time.LocalDateTime;

/**
 * 文档 DTO（返回给前端）
 */
@Data
public class DocumentDTO {

    private Long id;
    private String tenantId;
    private String fileName;
    private String objectKey;
    private String docType;
    private String status;
    private Integer pageCount;
    private Integer chunkCount;
    private LocalDateTime createdAt;
}
