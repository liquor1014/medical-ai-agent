package com.medicalai.common;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.regex.Pattern;

/**
 * 角色配置管理服务
 * - 仅 super_admin 可访问（由 AuthorizationInterceptor 拦截 /api/roles/**）
 * - 内置角色（is_builtin）不可删除、不可修改 code
 * - super_admin 角色不可修改、不可停用
 * - 删除角色前需确认无用户使用该角色
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class RoleConfigService {

    public static final String ROLE_SUPER_ADMIN = "super_admin";
    private static final Pattern CODE_PATTERN = Pattern.compile("^[a-z][a-z0-9_]{1,31}$");

    private final RoleRepository roleRepository;
    private final UserTenantRepository userTenantRepository;
    private final TenantPermissionRepository tenantPermissionRepository;

    public List<Role> list() {
        return roleRepository.findAll();
    }

    public Role create(Role role) {
        validateCode(role.getCode());
        if (role.getName() == null || role.getName().isBlank()) {
            throw new BusinessException(400, "角色名称不能为空");
        }
        role.setName(role.getName().trim());
        role.setDescription(role.getDescription() == null ? null : role.getDescription().trim());
        role.setStatus("enabled");
        role.setIsBuiltin(false);
        roleRepository.insert(role);
        // 为新角色写入默认业务权限
        tenantPermissionRepository.insertDefaultBusinessPermissions(role.getCode());
        log.info("创建角色: {}", role.getCode());
        return roleRepository.findByCode(role.getCode());
    }

    public Role update(String code, Role role) {
        Role existing = requireRole(code);
        // 内置角色仅允许修改名称/描述
        role.setCode(code);
        if (role.getName() == null || role.getName().isBlank()) {
            throw new BusinessException(400, "角色名称不能为空");
        }
        role.setName(role.getName().trim());
        role.setDescription(role.getDescription() == null ? null : role.getDescription().trim());
        roleRepository.update(role);
        log.info("更新角色: {}", code);
        return roleRepository.findByCode(code);
    }

    public void delete(String code) {
        Role existing = requireRole(code);
        if (Boolean.TRUE.equals(existing.getIsBuiltin())) {
            throw new BusinessException(400, "内置角色不允许删除");
        }
        if (ROLE_SUPER_ADMIN.equals(code)) {
            throw new BusinessException(400, "超级管理员角色不允许删除");
        }
        int used = userTenantRepository.countByRole(code);
        if (used > 0) {
            throw new BusinessException(409, "该角色已被 " + used + " 个用户使用，无法删除");
        }
        tenantPermissionRepository.deleteByRole(code);
        roleRepository.delete(code);
        log.info("删除角色: {}", code);
    }

    public Role toggleStatus(String code, String status) {
        Role existing = requireRole(code);
        if (ROLE_SUPER_ADMIN.equals(code)) {
            throw new BusinessException(400, "超级管理员角色不允许停用");
        }
        if (!"enabled".equals(status) && !"disabled".equals(status)) {
            throw new BusinessException(400, "状态值无效，仅支持 enabled / disabled");
        }
        roleRepository.updateStatus(code, status);
        log.info("角色 {} 状态变更为 {}", code, status);
        return roleRepository.findByCode(code);
    }

    private Role requireRole(String code) {
        Role role = roleRepository.findByCode(code);
        if (role == null) {
            throw new BusinessException(404, "角色不存在");
        }
        return role;
    }

    private void validateCode(String code) {
        if (code == null || !CODE_PATTERN.matcher(code).matches()) {
            throw new BusinessException(400, "角色编码需为 2-32 位小写字母、数字或下划线，且以字母开头");
        }
    }
}
