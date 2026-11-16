package com.medicalai.common;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;

/**
 * 租户内用户与角色管理服务
 * - 系统超级管理员（super_admin）：可跨租户管理所有用户与角色
 * - 租户管理员（tenant_admin）：仅可管理本租户内的用户与角色
 * - 普通医生（doctor）：无管理权限
 * 每个租户仅允许存在一个 tenant_admin（由部分唯一索引 + 业务层双重校验保证）
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class RoleService {

    public static final String ROLE_SUPER_ADMIN = "super_admin";
    public static final String ROLE_TENANT_ADMIN = "tenant_admin";
    public static final String ROLE_DOCTOR = "doctor";

    private final UserRepository userRepository;
    private final UserTenantRepository userTenantRepository;
    private final RoleRepository roleRepository;

    /**
     * 列出指定租户下的全部用户及其角色
     */
    public List<Map<String, Object>> listTenantUsers(String targetTenantId) {
        String tenantId = resolveAccessibleTenant(targetTenantId);
        return userRepository.findUsersByTenant(tenantId);
    }

    /**
     * 为用户在指定租户下分配 / 修改角色
     * - 若用户尚未绑定该租户，自动建立绑定
     * - 每个租户仅允许一个 tenant_admin，重复设置会抛 409
     * - 禁止将任何用户的角色修改为 super_admin（仅 superAdmin 账号硬编码持有）
     * - 禁止编辑 superAdmin 账号的角色
     */
    public void assignRole(Long userId, String targetTenantId, String role) {
        String tenantId = resolveAccessibleTenant(targetTenantId);

        // 禁止分配 super_admin 角色
        if (ROLE_SUPER_ADMIN.equals(role)) {
            throw new BusinessException(403, "禁止分配超级系统管理员角色");
        }

        // 角色合法性：查 role 表中启用的角色
        Role roleDef = roleRepository.findByCode(role);
        if (role == null || roleDef == null || !"enabled".equals(roleDef.getStatus())) {
            throw new BusinessException(400, "无效的角色: " + role);
        }

        UserAccount user = userRepository.findById(userId);
        if (user == null) {
            throw new BusinessException(404, "用户不存在");
        }

        // 禁止编辑 superAdmin 账号的角色
        if (UserContext.SUPER_ADMIN_USERNAME.equals(user.getUsername())) {
            throw new BusinessException(403, "禁止编辑超级管理员账号的角色");
        }

        UserTenant existing = userTenantRepository.findBinding(userId, tenantId);
        if (existing == null) {
            // 首次绑定：校验租户管理员唯一性
            if (ROLE_TENANT_ADMIN.equals(role)) {
                assertTenantAdminUnique(tenantId, null);
            }
            UserTenant binding = new UserTenant();
            binding.setUserId(userId);
            binding.setTenantId(tenantId);
            binding.setRole(role);
            userTenantRepository.insert(binding);
            log.info("用户 {} 绑定到租户 {}，角色 {}", userId, tenantId, role);
            return;
        }

        // 已绑定：仅当角色变更时处理唯一性约束
        if (!existing.getRole().equals(role)) {
            if (ROLE_TENANT_ADMIN.equals(role)) {
                assertTenantAdminUnique(tenantId, userId);
            }
            userTenantRepository.updateRole(userId, tenantId, role);
            log.info("用户 {} 在租户 {} 的角色变更为 {}", userId, tenantId, role);
        }
    }

    /**
     * 解除用户与租户的绑定
     */
    public void unbindUser(Long userId, String targetTenantId) {
        String tenantId = resolveAccessibleTenant(targetTenantId);
        UserAccount user = userRepository.findById(userId);
        if (user == null) {
            throw new BusinessException(404, "用户不存在");
        }
        // 不允许解除超级管理员自身在某租户的绑定（避免误删）
        if (UserContext.getUsername() != null && UserContext.getUsername().equals(user.getUsername())
                && UserContext.isSuperAdmin()) {
            throw new BusinessException(400, "不能解除超级管理员自身的租户绑定");
        }
        userTenantRepository.delete(userId, tenantId);
        log.info("解除用户 {} 与租户 {} 的绑定", userId, tenantId);
    }

    /**
     * 校验：指定租户内 tenant_admin 角色的用户数不超过 1
     * @param excludeUserId 排除正在修改的用户自身（角色变更场景）
     */
    private void assertTenantAdminUnique(String tenantId, Long excludeUserId) {
        int count = userTenantRepository.countByTenantAndRole(tenantId, ROLE_TENANT_ADMIN);
        if (count > 0) {
            // 若排除自身后仍有其他人是 tenant_admin，则不允许
            if (excludeUserId == null) {
                throw new BusinessException(409, "该租户已存在租户管理员，每租户仅允许一个");
            }
            UserTenant current = userTenantRepository.findBinding(excludeUserId, tenantId);
            if (current == null || !ROLE_TENANT_ADMIN.equals(current.getRole())) {
                throw new BusinessException(409, "该租户已存在租户管理员，每租户仅允许一个");
            }
        }
    }

    /**
     * 解析当前操作允许访问的目标租户：
     * - super_admin：使用请求指定的租户（未指定时回退到当前 token 租户）
     * - tenant_admin：强制锁定为当前 token 所属租户，禁止跨租户
     * - 其他角色：无权限
     */
    private String resolveAccessibleTenant(String targetTenantId) {
        if (UserContext.isSuperAdmin()) {
            if (targetTenantId != null && !targetTenantId.isBlank()) {
                return targetTenantId.trim();
            }
            String tokenTenant = TenantContext.getTenantId();
            return (tokenTenant == null || tokenTenant.isBlank()) ? null : tokenTenant;
        }
        if (UserContext.isTenantAdmin()) {
            String tokenTenant = TenantContext.getTenantId();
            if (targetTenantId != null && !targetTenantId.isBlank()
                    && !targetTenantId.trim().equals(tokenTenant)) {
                throw new BusinessException(403, "租户管理员仅能管理本租户内的用户");
            }
            return tokenTenant;
        }
        throw new BusinessException(403, "无权限执行该操作");
    }
}
