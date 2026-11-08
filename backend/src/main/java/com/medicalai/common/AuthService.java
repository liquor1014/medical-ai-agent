package com.medicalai.common;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

import java.util.UUID;

/**
 * 认证服务：数据库用户（app_user）+ BCrypt + JWT + Redis 会话
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AuthService {

    private final UserRepository userRepository;
    private final JwtTokenService jwtTokenService;
    private final SessionStore sessionStore;

    private final PasswordEncoder passwordEncoder = new BCryptPasswordEncoder();

    @Value("${app.tenant.default-tenant:hospital-demo}")
    private String defaultTenant;

    /**
     * 登录：校验数据库中的用户名/密码，签发 JWT，并在 Redis 中创建会话
     */
    public String login(String username, String password) {
        String tenantId = currentTenant();
        UserAccount user = userRepository.findByTenantAndUsername(tenantId, username);
        if (user == null || !passwordEncoder.matches(password, user.getPasswordHash())) {
            throw new BusinessException(401, "用户名或密码错误");
        }
        if (!"active".equalsIgnoreCase(user.getStatus())) {
            throw new BusinessException(403, "账号已被禁用");
        }
        log.info("用户登录成功: {}/{} (role={})", tenantId, user.getUsername(), user.getRole());
        return issueToken(user);
    }

    /**
     * 注册：在当前租户下创建用户，成功后直接签发 JWT（自动登录）
     */
    public String register(String username, String password, String displayName) {
        String tenantId = currentTenant();
        if (userRepository.findByTenantAndUsername(tenantId, username) != null) {
            throw new BusinessException(409, "用户名已存在");
        }

        UserAccount user = new UserAccount();
        user.setTenantId(tenantId);
        user.setUsername(username);
        user.setPasswordHash(passwordEncoder.encode(password));
        user.setDisplayName(displayName == null || displayName.isBlank() ? username : displayName.trim());
        user.setRole("doctor");
        user.setStatus("active");

        try {
            userRepository.insert(user);
        } catch (DuplicateKeyException e) {
            throw new BusinessException(409, "用户名已存在");
        }
        log.info("用户注册成功: {}/{}", tenantId, username);
        return issueToken(user);
    }

    private String currentTenant() {
        String tenantId = TenantContext.getTenantId();
        return (tenantId == null || tenantId.isBlank()) ? defaultTenant : tenantId;
    }

    private String issueToken(UserAccount user) {
        String jti = UUID.randomUUID().toString().replace("-", "");
        String token = jwtTokenService.createToken(user, jti);
        sessionStore.save(jti, user.getUsername(), jwtTokenService.getTtl());
        return token;
    }

    /**
     * 校验 Token：JWT 签名/有效期 + Redis 会话是否仍存在（登出后失效）
     */
    public JwtTokenService.TokenPayload verify(String token) {
        JwtTokenService.TokenPayload payload = jwtTokenService.parse(token);
        if (payload == null || !sessionStore.exists(payload.jti())) {
            return null;
        }
        return payload;
    }

    /**
     * 登出：仅吊销当前 Token 的 Redis 会话
     */
    public void logout(String token) {
        JwtTokenService.TokenPayload payload = jwtTokenService.parse(token);
        if (payload != null) {
            sessionStore.remove(payload.jti());
            log.info("用户登出: {}/{}", payload.tenantId(), payload.username());
        }
    }
}
