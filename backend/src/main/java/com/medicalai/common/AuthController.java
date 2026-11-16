package com.medicalai.common;

import com.medicalai.common.dto.ChangePasswordRequest;
import com.medicalai.common.dto.ForgotCodeRequest;
import com.medicalai.common.dto.ForgotCodeResponse;
import com.medicalai.common.dto.LoginRequest;
import com.medicalai.common.dto.LoginResponse;
import com.medicalai.common.dto.RegisterRequest;
import com.medicalai.common.dto.ResetPasswordRequest;
import com.medicalai.common.dto.VerifyCodeRequest;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * 认证接口：登录 / 注册 / 登出 + 密码找回与修改
 */
@RestController
@RequestMapping("/api/auth")
@RequiredArgsConstructor
public class AuthController {

    private final AuthService authService;
    private final PasswordResetService passwordResetService;
    private final PasswordPolicy passwordPolicy;

    @PostMapping("/login")
    public Result<LoginResponse> login(@Valid @RequestBody LoginRequest req) {
        return Result.success(authService.login(req.getUsername().trim(), req.getPassword(),
                req.getTenantId()));
    }

    @PostMapping("/register")
    public Result<LoginResponse> register(@Valid @RequestBody RegisterRequest req) {
        String username = req.getUsername().trim();
        return Result.success(authService.register(username, req.getPassword(),
                req.getDisplayName(), req.getEmail(), req.getTenantId()));
    }

    @PostMapping("/logout")
    public Result<Void> logout(HttpServletRequest request) {
        String token = request.getHeader("Authorization");
        if (token != null && token.startsWith("Bearer ")) {
            token = token.substring(7);
        }
        authService.logout(token);
        return Result.success();
    }

    @GetMapping("/me")
    public Result<String> me() {
        return Result.success(UserContext.getUsername());
    }

    /**
     * 获取当前登录用户的权限码列表（供前端动态菜单渲染使用）
     */
    @GetMapping("/permissions")
    public Result<List<String>> permissions() {
        return Result.success(authService.getCurrentPermissions());
    }

    /**
     * 密码复杂度规则（公开，供前端实时提示使用）
     */
    @GetMapping("/password/policy")
    public Result<Map<String, Object>> passwordPolicy() {
        return Result.success(passwordPolicy.describe());
    }

    /**
     * 找回密码第一步：校验用户名 + 邮箱并发送验证码
     */
    @PostMapping("/password/forgot-code")
    public Result<ForgotCodeResponse> forgotCode(@Valid @RequestBody ForgotCodeRequest req) {
        return Result.success(passwordResetService.sendCode(req.getTenantId(),
                req.getUsername().trim(), req.getEmail()));
    }

    /**
     * 找回密码第二步：校验验证码，换取一次性重置凭证
     */
    @PostMapping("/password/verify-code")
    public Result<String> verifyCode(@Valid @RequestBody VerifyCodeRequest req) {
        String ticket = passwordResetService.verifyCode(req.getTenantId(),
                req.getUsername().trim(), req.getEmail(), req.getCode());
        return Result.success(ticket);
    }

    /**
     * 找回密码第三步：提交新密码
     */
    @PostMapping("/password/reset")
    public Result<Void> resetPassword(@Valid @RequestBody ResetPasswordRequest req) {
        passwordResetService.resetPassword(req.getTenantId(), req.getUsername().trim(),
                req.getResetTicket(), req.getNewPassword());
        return Result.success();
    }

    /**
     * 登录态修改密码
     */
    @PostMapping("/password/change")
    public Result<Void> changePassword(@Valid @RequestBody ChangePasswordRequest req,
                                       HttpServletRequest request) {
        String token = request.getHeader("Authorization");
        if (token != null && token.startsWith("Bearer ")) {
            token = token.substring(7);
        }
        authService.changePassword(req.getOldPassword(), req.getNewPassword(), token);
        return Result.success();
    }
}
