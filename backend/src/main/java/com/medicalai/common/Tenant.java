package com.medicalai.common;

import lombok.Data;

import java.time.OffsetDateTime;

/**
 * 租户（tenant 表）
 */
@Data
public class Tenant {
    private String id;
    private String name;
    private String description;
    private String status;
    private int sortOrder;
    private int userCount;
    private OffsetDateTime createdAt;
    private OffsetDateTime updatedAt;
}
