package com.medicalai.file.entity;

import lombok.Data;

import java.time.LocalDateTime;

/**
 * 文档实体（对应 document 表）
 */
@Data
public class Document {

    private Long id;
    private String tenantId;
    private String fileName;
    private String objectKey;
    private String docType;
    private String status;      // pending / parsing / completed / failed
    private Integer pageCount;
    private Integer chunkCount;
    private LocalDateTime createdAt;
}
