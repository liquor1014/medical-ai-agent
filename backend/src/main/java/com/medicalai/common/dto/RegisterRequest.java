package com.medicalai.common.dto;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import lombok.Data;

/**
 * 注册请求
 */
@Data
public class RegisterRequest {

    @NotBlank(message = "用户名不能为空")
    @Pattern(regexp = "^[A-Za-z0-9_]{3,32}$", message = "用户名仅支持 3-32 位字母、数字或下划线")
    private String username;

    @NotBlank(message = "密码不能为空")
    @Size(max = 64, message = "密码长度不能超过 64 位")
    private String password;

    @Size(max = 64, message = "昵称长度不能超过 64 位")
    private String displayName;

    @Email(message = "邮箱格式不正确")
    @Size(max = 128, message = "邮箱长度不能超过 128 位")
    private String email;

    /**
     * 注册时选择的租户 ID，注册成功后自动建立用户与该租户的绑定关系
     */
    private String tenantId;
}
