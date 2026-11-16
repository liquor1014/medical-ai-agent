package com.medicalai.common;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * 角色配置管理单元测试
 */
@ExtendWith(MockitoExtension.class)
class RoleConfigServiceTest {

    @Mock
    private RoleRepository roleRepository;
    @Mock
    private UserTenantRepository userTenantRepository;
    @Mock
    private TenantPermissionRepository tenantPermissionRepository;

    @InjectMocks
    private RoleConfigService roleConfigService;

    private Role role(String code, boolean builtin) {
        Role r = new Role();
        r.setCode(code);
        r.setName(code);
        r.setStatus("enabled");
        r.setIsBuiltin(builtin);
        return r;
    }

    @Test
    void create_shouldInsertRoleAndDefaultPermissions() {
        when(roleRepository.findByCode("custom_role")).thenReturn(role("custom_role", false));
        Role input = role("custom_role", false);

        Role result = roleConfigService.create(input);

        assertThat(result.getCode()).isEqualTo("custom_role");
        verify(roleRepository).insert(any(Role.class));
        verify(tenantPermissionRepository).insertDefaultBusinessPermissions("custom_role");
    }

    @Test
    void create_shouldThrow400_forInvalidCode() {
        Role input = role("Invalid_Code!", false);
        assertThatThrownBy(() -> roleConfigService.create(input))
                .isInstanceOf(BusinessException.class)
                .hasMessageContaining("角色编码")
                .satisfies(e -> assertThat(((BusinessException) e).getCode()).isEqualTo(400));
    }

    @Test
    void delete_shouldThrow400_forBuiltinRole() {
        when(roleRepository.findByCode("doctor")).thenReturn(role("doctor", true));

        assertThatThrownBy(() -> roleConfigService.delete("doctor"))
                .isInstanceOf(BusinessException.class)
                .hasMessage("内置角色不允许删除")
                .satisfies(e -> assertThat(((BusinessException) e).getCode()).isEqualTo(400));
        verify(roleRepository, never()).delete(anyString());
    }

    @Test
    void delete_shouldThrow400_forSuperAdminRole() {
        when(roleRepository.findByCode("super_admin")).thenReturn(role("super_admin", true));

        assertThatThrownBy(() -> roleConfigService.delete("super_admin"))
                .isInstanceOf(BusinessException.class)
                .hasMessage("内置角色不允许删除");
    }

    @Test
    void delete_shouldThrow409_whenRoleInUse() {
        when(roleRepository.findByCode("custom_role")).thenReturn(role("custom_role", false));
        when(userTenantRepository.countByRole("custom_role")).thenReturn(3);

        assertThatThrownBy(() -> roleConfigService.delete("custom_role"))
                .isInstanceOf(BusinessException.class)
                .hasMessageContaining("已被 3 个用户使用")
                .satisfies(e -> assertThat(((BusinessException) e).getCode()).isEqualTo(409));
        verify(roleRepository, never()).delete(anyString());
    }

    @Test
    void delete_shouldSucceed_whenRoleNotInUse() {
        when(roleRepository.findByCode("custom_role")).thenReturn(role("custom_role", false));
        when(userTenantRepository.countByRole("custom_role")).thenReturn(0);

        roleConfigService.delete("custom_role");

        verify(tenantPermissionRepository).deleteByRole("custom_role");
        verify(roleRepository).delete("custom_role");
    }

    @Test
    void toggleStatus_shouldThrow400_forSuperAdmin() {
        when(roleRepository.findByCode("super_admin")).thenReturn(role("super_admin", true));

        assertThatThrownBy(() -> roleConfigService.toggleStatus("super_admin", "disabled"))
                .isInstanceOf(BusinessException.class)
                .hasMessage("超级管理员角色不允许停用");
    }

    @Test
    void toggleStatus_shouldUpdateStatus() {
        when(roleRepository.findByCode("custom_role")).thenReturn(role("custom_role", false));

        roleConfigService.toggleStatus("custom_role", "disabled");

        verify(roleRepository).updateStatus("custom_role", "disabled");
    }
}
