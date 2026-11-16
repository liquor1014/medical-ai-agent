package com.medicalai.common.dto;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import lombok.Data;

/**
 * 找回密码：发送验证码请求
 */
@Data
public class ForgotCodeRequest {

    private String tenantId;

    @NotBlank(message = "请输入用户名")
    private String username;

    @NotBlank(message = "请输入绑定邮箱")
    @Email(message = "邮箱格式不正确")
    private String email;
}
