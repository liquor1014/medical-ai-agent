package com.medicalai.common.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Data;

/**
 * 找回密码：提交新密码请求
 */
@Data
public class ResetPasswordRequest {

    private String tenantId;

    @NotBlank(message = "请输入用户名")
    private String username;

    @NotBlank(message = "重置凭证不能为空")
    private String resetTicket;

    @NotBlank(message = "请输入新密码")
    @Size(max = 64, message = "密码长度不能超过 64 位")
    private String newPassword;
}
