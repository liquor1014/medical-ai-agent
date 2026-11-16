package com.medicalai.common.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

@Data
public class LoginRequest {

    @NotBlank(message = "用户名不能为空")
    private String username;

    @NotBlank(message = "密码不能为空")
    private String password;

    /**
     * 登录租户 ID：优先级高于 X-Tenant-Id 请求头；为空时回退到用户归属租户
     */
    private String tenantId;
}
