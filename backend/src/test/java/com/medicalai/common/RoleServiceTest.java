package com.medicalai.common;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.lenient;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * 角色管理单元测试：租户管理员唯一性 + 跨租户越权拦截
 */
@ExtendWith(MockitoExtension.class)
class RoleServiceTest {

    private static final String TENANT_A = "hospital-a";
    private static final String TENANT_B = "hospital-b";

    @Mock
    private UserRepository userRepository;
    @Mock
    private UserTenantRepository userTenantRepository;
    @Mock
    private RoleRepository roleRepository;

    private RoleService roleService;

    @BeforeEach
    void setUp() {
        roleService = new RoleService(userRepository, userTenantRepository, roleRepository);
        lenient().when(roleRepository.findByCode("doctor")).thenReturn(enabledRole("doctor"));
        lenient().when(roleRepository.findByCode("tenant_admin")).thenReturn(enabledRole("tenant_admin"));
    }

    private Role enabledRole(String code) {
        Role r = new Role();
        r.setCode(code);
        r.setName(code);
        r.setStatus("enabled");
        r.setIsBuiltin(false);
        return r;
    }

    @AfterEach
    void tearDown() {
        UserContext.clear();
        TenantContext.clear();
    }

    private void asSuperAdmin(String tenant) {
        UserContext.setUsername("admin");
        UserContext.setRole("super_admin");
        TenantContext.setTenantId(tenant);
    }

    private void asTenantAdmin(String tenant) {
        UserContext.setUsername("ta");
        UserContext.setRole("tenant_admin");
        TenantContext.setTenantId(tenant);
    }

    private void asDoctor(String tenant) {
        UserContext.setUsername("doc");
        UserContext.setRole("doctor");
        TenantContext.setTenantId(tenant);
    }

    private UserAccount user(Long id) {
        UserAccount u = new UserAccount();
        u.setId(id);
        u.setUsername("user" + id);
        return u;
    }

    // ========== 租户管理员唯一性 ==========

    @Test
    void assignRole_shouldThrow409_whenTenantAdminAlreadyExists() {
        asSuperAdmin(TENANT_A);
        when(userRepository.findById(10L)).thenReturn(user(10L));
        when(userTenantRepository.findBinding(10L, TENANT_A)).thenReturn(null);
        // 该租户已存在一个 tenant_admin
        when(userTenantRepository.countByTenantAndRole(TENANT_A, "tenant_admin")).thenReturn(1);

        assertThatThrownBy(() -> roleService.assignRole(10L, TENANT_A, "tenant_admin"))
                .isInstanceOf(BusinessException.class)
                .hasMessage("该租户已存在租户管理员，每租户仅允许一个")
                .satisfies(e -> assertThat(((BusinessException) e).getCode()).isEqualTo(409));

        verify(userTenantRepository, never()).insert(any(UserTenant.class));
        verify(userTenantRepository, never()).updateRole(eq(10L), eq(TENANT_A), anyString());
    }

    @Test
    void assignRole_shouldAllowTenantAdminWhenCountIsZero() {
        asSuperAdmin(TENANT_A);
        when(userRepository.findById(10L)).thenReturn(user(10L));
        when(userTenantRepository.findBinding(10L, TENANT_A)).thenReturn(null);
        when(userTenantRepository.countByTenantAndRole(TENANT_A, "tenant_admin")).thenReturn(0);

        roleService.assignRole(10L, TENANT_A, "tenant_admin");

        verify(userTenantRepository).insert(any(UserTenant.class));
    }

    @Test
    void assignRole_shouldAllowChangingOtherRolesWhenAdminExists() {
        asSuperAdmin(TENANT_A);
        when(userRepository.findById(10L)).thenReturn(user(10L));
        when(userTenantRepository.findBinding(10L, TENANT_A)).thenReturn(null);
        // tenant_admin 已存在，但目标角色是 doctor，不受唯一性约束

        roleService.assignRole(10L, TENANT_A, "doctor");

        verify(userTenantRepository).insert(any(UserTenant.class));
    }

    // ========== 跨租户越权拦截 ==========

    @Test
    void tenantAdmin_shouldThrow403_whenManagingOtherTenant() {
        asTenantAdmin(TENANT_A);

        assertThatThrownBy(() -> roleService.assignRole(10L, TENANT_B, "doctor"))
                .isInstanceOf(BusinessException.class)
                .hasMessage("租户管理员仅能管理本租户内的用户")
                .satisfies(e -> assertThat(((BusinessException) e).getCode()).isEqualTo(403));
    }

    @Test
    void tenantAdmin_shouldBeAbleToManageOwnTenant() {
        asTenantAdmin(TENANT_A);
        when(userRepository.findById(10L)).thenReturn(user(10L));
        when(userTenantRepository.findBinding(10L, TENANT_A)).thenReturn(null);

        roleService.assignRole(10L, TENANT_A, "doctor");

        verify(userTenantRepository).insert(any(UserTenant.class));
    }

    @Test
    void doctor_shouldThrow403_whenManagingUsers() {
        asDoctor(TENANT_A);

        assertThatThrownBy(() -> roleService.assignRole(10L, TENANT_A, "doctor"))
                .isInstanceOf(BusinessException.class)
                .hasMessage("无权限执行该操作")
                .satisfies(e -> assertThat(((BusinessException) e).getCode()).isEqualTo(403));
    }

    @Test
    void superAdmin_shouldBeAbleToAssignRoleAcrossTenants() {
        asSuperAdmin(TENANT_A);
        when(userRepository.findById(10L)).thenReturn(user(10L));
        when(userTenantRepository.findBinding(10L, TENANT_B)).thenReturn(null);

        // 超级管理员跨租户分配角色
        roleService.assignRole(10L, TENANT_B, "doctor");

        verify(userTenantRepository).insert(any(UserTenant.class));
    }

    @Test
    void assignRole_shouldThrow400_forInvalidRole() {
        asSuperAdmin(TENANT_A);

        assertThatThrownBy(() -> roleService.assignRole(10L, TENANT_A, "super_duper_admin"))
                .isInstanceOf(BusinessException.class)
                .hasMessageContaining("无效的角色")
                .satisfies(e -> assertThat(((BusinessException) e).getCode()).isEqualTo(400));
    }

    @Test
    void assignRole_shouldThrow403_whenNonSuperAdminGrantsSuperAdmin() {
        asTenantAdmin(TENANT_A);

        assertThatThrownBy(() -> roleService.assignRole(10L, TENANT_A, "super_admin"))
                .isInstanceOf(BusinessException.class)
                .hasMessage("禁止分配超级系统管理员角色")
                .satisfies(e -> assertThat(((BusinessException) e).getCode()).isEqualTo(403));
    }

    @Test
    void assignRole_shouldThrow403_whenEditingSuperAdminAccount() {
        asSuperAdmin(TENANT_A);
        UserAccount superAdmin = user(99L);
        superAdmin.setUsername(UserContext.SUPER_ADMIN_USERNAME);
        when(userRepository.findById(99L)).thenReturn(superAdmin);

        assertThatThrownBy(() -> roleService.assignRole(99L, TENANT_A, "doctor"))
                .isInstanceOf(BusinessException.class)
                .hasMessage("禁止编辑超级管理员账号的角色")
                .satisfies(e -> assertThat(((BusinessException) e).getCode()).isEqualTo(403));
    }
}
