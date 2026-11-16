package com.medicalai.common.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Data;

/**
 * 修改密码请求（登录态）
 */
@Data
public class ChangePasswordRequest {

    @NotBlank(message = "请输入原密码")
    private String oldPassword;

    @NotBlank(message = "请输入新密码")
    @Size(max = 64, message = "密码长度不能超过 64 位")
    private String newPassword;
}
