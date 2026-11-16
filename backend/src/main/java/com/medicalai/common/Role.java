package com.medicalai.common;

import lombok.Data;

import java.time.OffsetDateTime;

/**
 * 角色配置实体
 */
@Data
public class Role {
    private String code;
    private String name;
    private String description;
    private String status; // enabled / disabled
    private Boolean isBuiltin;
    private OffsetDateTime createdAt;
    private OffsetDateTime updatedAt;
}
