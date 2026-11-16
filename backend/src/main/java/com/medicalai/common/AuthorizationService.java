package com.medicalai.common;

import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.Set;

/**
 * 全局授权服务：根据请求路径解析所需权限，并基于租户-角色-权限映射表进行校验
 * - super_admin：全平台放行
 * - 其他角色：按当前 token 租户 + 角色查询 tenant_permission 表
 */
@Service
@RequiredArgsConstructor
public class AuthorizationService {

    private final TenantPermissionRepository permissionRepository;

    /**
     * 路径前缀 → 所需权限 的映射
     * 顺序敏感：越长的前缀越靠前
     */
    private static final String[][] PATH_PERMISSIONS = {
            {"/api/tenants/admin", "system:tenant"},
            {"/api/roles", "system:role"},
            {"/api/admin/users", "system:user"},
            {"/api/audit", "system:audit"},
            {"/api/files", "business:files"},
            {"/api/chat", "business:chat"},
            {"/api/reports", "business:reports"},
            {"/api/models", "business:models"},
            {"/api/eval", "business:eval"},
    };

    /**
     * 根据请求路径解析所需权限（无匹配返回 null，表示仅需登录态）
     */
    public String resolvePermission(String requestUri) {
        if (requestUri == null) {
            return null;
        }
        for (String[] rule : PATH_PERMISSIONS) {
            if (requestUri.startsWith(rule[0])) {
                return rule[1];
            }
        }
        return null;
    }

    /**
     * 校验当前用户是否有权限访问指定资源
     *
     * @param permission 所需权限（null 表示仅需登录）
     * @return true 表示放行
     */
    public boolean hasPermission(String permission) {
        // super_admin 全平台放行
        if (UserContext.isSuperAdmin()) {
            return true;
        }
        if (permission == null) {
            return true;
        }
        String tenantId = TenantContext.getTenantId();
        String role = UserContext.getRole();
        if (tenantId == null || role == null) {
            return false;
        }
        Set<String> perms = permissionRepository.findPermissions(tenantId, role);
        return perms.contains(permission);
    }
}
