package com.medicalai.common.dto;

import lombok.AllArgsConstructor;
import lombok.Data;

/**
 * 找回密码：发送验证码结果
 */
@Data
@AllArgsConstructor
public class ForgotCodeResponse {

    /** 邮件是否已真实发送 */
    private boolean delivered;

    /** 演示环境（未配置 SMTP）直接返回验证码，便于本地体验；生产环境为 null */
    private String demoCode;

    /** 验证码有效期（秒） */
    private int expiresInSeconds;
}
