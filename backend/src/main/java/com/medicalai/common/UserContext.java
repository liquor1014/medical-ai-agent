package com.medicalai.common;

/**
 * 当前登录用户上下文
 */
public class UserContext {

    /** 系统超级管理员账号（硬编码，唯一拥有 super_admin 角色） */
    public static final String SUPER_ADMIN_USERNAME = "superAdmin";

    private static final ThreadLocal<String> USERNAME = new ThreadLocal<>();
    private static final ThreadLocal<String> ROLE = new ThreadLocal<>();

    public static void setUsername(String username) {
        USERNAME.set(username);
    }

    public static String getUsername() {
        return USERNAME.get();
    }

    public static void setRole(String role) {
        ROLE.set(role);
    }

    public static String getRole() {
        return ROLE.get();
    }

    public static boolean isSuperAdmin() {
        return "super_admin".equalsIgnoreCase(ROLE.get());
    }

    public static boolean isTenantAdmin() {
        return "tenant_admin".equalsIgnoreCase(ROLE.get());
    }

    /**
     * 管理端接口统一鉴权：仅系统超级管理员可操作（如租户管理）
     */
    public static void requireSuperAdmin() {
        if (!isSuperAdmin()) {
            throw new BusinessException(403, "无权限访问，仅系统超级管理员可操作");
        }
    }

    public static void clear() {
        USERNAME.remove();
        ROLE.remove();
    }
}
