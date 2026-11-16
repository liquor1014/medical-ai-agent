package com.medicalai.common;

import com.medicalai.common.dto.LoginResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Set;
import java.util.UUID;

/**
 * 认证服务：数据库用户（app_user）+ BCrypt + JWT + Redis 会话 + 多租户绑定
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AuthService {

    private final UserRepository userRepository;
    private final UserTenantRepository userTenantRepository;
    private final JwtTokenService jwtTokenService;
    private final SessionStore sessionStore;
    private final PasswordEncoder passwordEncoder;
    private final PasswordPolicy passwordPolicy;
    private final LoginSecurityService loginSecurityService;
    private final TenantPermissionRepository tenantPermissionRepository;

    @Value("${app.tenant.default-tenant:hospital-demo}")
    private String defaultTenant;

    /**
     * 登录：校验密码 -> 校验用户与所选租户的绑定关系 -> 签发 JWT
     * tenantId 优先级：请求体 > 请求头 X-Tenant-Id > 用户归属租户
     */
    public LoginResponse login(String username, String password, String requestTenantId) {
        UserAccount user = userRepository.findByUsername(username);
        if (user == null) {
            throw new BusinessException(401, "用户名或密码错误");
        }
        loginSecurityService.assertNotLocked(user);
        if (!passwordEncoder.matches(password, user.getPasswordHash())) {
            loginSecurityService.recordFailure(user);
        }
        if (!"active".equalsIgnoreCase(user.getStatus())) {
            throw new BusinessException(403, "账号已被禁用");
        }

        String tenantId = resolveTenant(requestTenantId, user.getTenantId());

        // 校验用户是否绑定到所选租户
        UserTenant binding = userTenantRepository.findBinding(user.getId(), tenantId);
        if (binding == null) {
            throw new BusinessException(403, "您未加入该租户，请联系管理员授权");
        }
        // superAdmin 账号硬编码：角色恒为 super_admin
        String role = UserContext.SUPER_ADMIN_USERNAME.equals(username)
                ? RoleService.ROLE_SUPER_ADMIN : binding.getRole();

        loginSecurityService.recordSuccess(user);
        log.info("用户登录成功: {}@{}, role={}", username, tenantId, role);
        return buildLoginResponse(user, tenantId, role);
    }

    /**
     * 注册：创建全局用户并自动绑定到所选租户（角色默认 doctor），成功后签发 JWT
     */
    public LoginResponse register(String username, String password, String displayName, String email,
                                  String requestTenantId) {
        String tenantId = (requestTenantId != null && !requestTenantId.isBlank())
                ? requestTenantId.trim() : currentTenant();
        passwordPolicy.validate(password);
        if (userRepository.findByUsername(username) != null) {
            throw new BusinessException(409, "用户名已存在");
        }

        UserAccount user = new UserAccount();
        user.setTenantId(tenantId);
        user.setUsername(username);
        user.setPasswordHash(passwordEncoder.encode(password));
        user.setDisplayName(displayName == null || displayName.isBlank() ? username : displayName.trim());
        user.setRole("doctor");
        user.setStatus("active");
        user.setEmail(email == null || email.isBlank() ? null : email.trim().toLowerCase());

        long userId;
        try {
            userId = userRepository.insert(user);
        } catch (org.springframework.dao.DuplicateKeyException e) {
            throw new BusinessException(409, "用户名已存在");
        }

        // 自动建立用户与所选租户的绑定关系
        UserTenant binding = new UserTenant();
        binding.setUserId(userId);
        binding.setTenantId(tenantId);
        binding.setRole("doctor");
        userTenantRepository.insert(binding);

        log.info("用户注册成功: {}@{}", username, tenantId);
        return buildLoginResponse(user, tenantId, "doctor");
    }

    /**
     * 修改密码（登录态）：校验原密码 + 新密码复杂度，成功后吊销当前用户的其他会话
     */
    public void changePassword(String oldPassword, String newPassword, String token) {
        String username = UserContext.getUsername();
        UserAccount user = userRepository.findByUsername(username);
        if (user == null) {
            throw new BusinessException(401, "登录用户不存在，请重新登录");
        }
        if (!passwordEncoder.matches(oldPassword, user.getPasswordHash())) {
            throw new BusinessException(400, "原密码不正确");
        }
        passwordPolicy.validate(newPassword);
        if (passwordEncoder.matches(newPassword, user.getPasswordHash())) {
            throw new BusinessException(400, "新密码不能与原密码相同");
        }
        userRepository.updatePassword(username, passwordEncoder.encode(newPassword));
        userRepository.clearLoginState(username);
        JwtTokenService.TokenPayload payload = jwtTokenService.parse(token);
        sessionStore.removeOtherSessions(username, payload == null ? null : payload.jti());
        log.info("用户修改密码成功: {}", username);
    }

    private String resolveTenant(String requestTenantId, String homeTenant) {
        if (requestTenantId != null && !requestTenantId.isBlank()) {
            return requestTenantId.trim();
        }
        String headerTenant = TenantContext.getTenantId();
        if (headerTenant != null && !headerTenant.isBlank()) {
            return headerTenant.trim();
        }
        return (homeTenant == null || homeTenant.isBlank()) ? defaultTenant : homeTenant;
    }

    private String currentTenant() {
        String tenantId = TenantContext.getTenantId();
        return (tenantId == null || tenantId.isBlank()) ? defaultTenant : tenantId;
    }

    private LoginResponse buildLoginResponse(UserAccount user, String tenantId, String role) {
        String jti = UUID.randomUUID().toString().replace("-", "");
        String token = jwtTokenService.createToken(user, tenantId, role, jti);
        sessionStore.save(jti, tenantId, user.getUsername(), jwtTokenService.getTtl());
        List<String> permissions = resolvePermissions(tenantId, role);
        return new LoginResponse(token, user.getUsername(), tenantId, role, user.getDisplayName(), permissions);
    }

    /**
     * 获取当前登录用户的权限码列表（super_admin 返回全量权限码）
     * 注意：角色从数据库实时查询，而非使用 JWT 中存储的旧角色，
     * 以支持角色切换后无需重新登录即可刷新权限。
     */
    public List<String> getCurrentPermissions() {
        String username = UserContext.getUsername();
        String tenantId = TenantContext.getTenantId();
        if (UserContext.SUPER_ADMIN_USERNAME.equals(username)) {
            return resolvePermissions(tenantId, RoleService.ROLE_SUPER_ADMIN);
        }
        if (username == null || tenantId == null) {
            return List.of();
        }
        UserAccount user = userRepository.findByUsername(username);
        if (user == null) {
            return List.of();
        }
        UserTenant binding = userTenantRepository.findBinding(user.getId(), tenantId);
        String role = binding != null ? binding.getRole() : null;
        return resolvePermissions(tenantId, role);
    }

    private List<String> resolvePermissions(String tenantId, String role) {
        if (RoleService.ROLE_SUPER_ADMIN.equals(role)) {
            // super_admin 全平台权限：返回所有已知权限码
            return List.of("business:files", "business:chat", "business:reports",
                    "business:models", "business:eval", "system:audit", "system:user",
                    "system:tenant", "system:role");
        }
        if (tenantId == null || role == null) {
            return List.of();
        }
        Set<String> perms = tenantPermissionRepository.findPermissions(tenantId, role);
        return List.copyOf(perms);
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
            log.info("用户登出: {}@{}", payload.username(), payload.tenantId());
        }
    }
}
