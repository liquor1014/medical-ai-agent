package com.medicalai.common;

import lombok.Data;

import java.time.OffsetDateTime;

/**
 * 用户-租户绑定关系（多对多，每个用户在每个租户下有独立角色）
 */
@Data
public class UserTenant {
    private Long userId;
    private String tenantId;
    private String role;
    private OffsetDateTime createdAt;
}
