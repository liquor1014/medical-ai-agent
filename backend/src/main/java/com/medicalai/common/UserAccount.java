package com.medicalai.common;

import lombok.Data;

/**
 * 数据库用户账号（app_user 表）
 */
@Data
public class UserAccount {
    private Long id;
    private String tenantId;
    private String username;
    private String passwordHash;
    private String displayName;
    private String role;
    private String status;
}
