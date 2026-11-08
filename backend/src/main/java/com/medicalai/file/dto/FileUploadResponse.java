package com.medicalai.file.dto;

import lombok.AllArgsConstructor;
import lombok.Data;

/**
 * 文件上传响应
 */
@Data
@AllArgsConstructor
public class FileUploadResponse {
    private Long id;
    private String fileName;
    private String status;
}
