package com.medicalai.common.dto;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import lombok.Data;

/**
 * 找回密码：校验验证码请求
 */
@Data
public class VerifyCodeRequest {

    private String tenantId;

    @NotBlank(message = "请输入用户名")
    private String username;

    @NotBlank(message = "请输入绑定邮箱")
    @Email(message = "邮箱格式不正确")
    private String email;

    @NotBlank(message = "请输入验证码")
    @Pattern(regexp = "^\\d{6}$", message = "验证码为 6 位数字")
    private String code;
}
