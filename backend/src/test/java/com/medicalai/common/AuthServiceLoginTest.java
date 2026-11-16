package com.medicalai.common;

import com.medicalai.common.dto.LoginResponse;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.util.ReflectionTestUtils;

import java.time.Duration;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

/**
 * 登录功能单元测试：含租户绑定校验
 */
@ExtendWith(MockitoExtension.class)
class AuthServiceLoginTest {

    private static final String TENANT = "hospital-demo";
    private static final String OTHER_TENANT = "hospital-other";
    private static final String PASSWORD = "Nurse@123";
    private static final Duration TOKEN_TTL = Duration.ofHours(12);

    @Mock
    private UserRepository userRepository;
    @Mock
    private UserTenantRepository userTenantRepository;
    @Mock
    private TenantPermissionRepository tenantPermissionRepository;
    @Mock
    private JwtTokenService jwtTokenService;
    @Mock
    private SessionStore sessionStore;
    @Mock
    private LoginSecurityService loginSecurityService;

    private final PasswordEncoder passwordEncoder = new BCryptPasswordEncoder();
    private final PasswordPolicy passwordPolicy = new PasswordPolicy();

    private AuthService authService;

    @BeforeEach
    void setUp() {
        ReflectionTestUtils.setField(passwordPolicy, "minLength", 8);
        ReflectionTestUtils.setField(passwordPolicy, "maxLength", 64);
        ReflectionTestUtils.setField(passwordPolicy, "minClasses", 3);
        authService = new AuthService(userRepository, userTenantRepository, jwtTokenService, sessionStore,
                passwordEncoder, passwordPolicy, loginSecurityService, tenantPermissionRepository);
        ReflectionTestUtils.setField(authService, "defaultTenant", TENANT);
        TenantContext.setTenantId(TENANT);
    }

    @AfterEach
    void tearDown() {
        TenantContext.clear();
        UserContext.clear();
    }

    private UserAccount buildUser() {
        UserAccount u = new UserAccount();
        u.setId(42L);
        u.setUsername("nurse01");
        u.setPasswordHash(passwordEncoder.encode(PASSWORD));
        u.setTenantId(TENANT);
        u.setRole("doctor");
        u.setStatus("active");
        u.setDisplayName("护士小王");
        return u;
    }

    private UserTenant binding(String role) {
        UserTenant ut = new UserTenant();
        ut.setUserId(42L);
        ut.setTenantId(TENANT);
        ut.setRole(role);
        return ut;
    }

    @Test
    void login_shouldSucceed_whenUserBoundToTenant() {
        UserAccount user = buildUser();
        when(userRepository.findByUsername("nurse01")).thenReturn(user);
        when(userTenantRepository.findBinding(42L, TENANT)).thenReturn(binding("doctor"));
        when(tenantPermissionRepository.findPermissions(anyString(), anyString()))
                .thenReturn(java.util.Set.of("business:files"));
        when(jwtTokenService.createToken(any(UserAccount.class), anyString(), anyString(), anyString()))
                .thenReturn("jwt-token");
        when(jwtTokenService.getTtl()).thenReturn(TOKEN_TTL);

        LoginResponse response = authService.login("nurse01", PASSWORD, TENANT);

        assertThat(response.getToken()).isEqualTo("jwt-token");
        assertThat(response.getTenantId()).isEqualTo(TENANT);
        assertThat(response.getRole()).isEqualTo("doctor");
        verify(loginSecurityService).recordSuccess(user);
    }

    @Test
    void login_shouldThrow403_whenUserNotBoundToRequestedTenant() {
        UserAccount user = buildUser();
        when(userRepository.findByUsername("nurse01")).thenReturn(user);
        // 用户未绑定 OTHER_TENANT
        when(userTenantRepository.findBinding(42L, OTHER_TENANT)).thenReturn(null);

        assertThatThrownBy(() -> authService.login("nurse01", PASSWORD, OTHER_TENANT))
                .isInstanceOf(BusinessException.class)
                .hasMessage("您未加入该租户，请联系管理员授权")
                .satisfies(e -> assertThat(((BusinessException) e).getCode()).isEqualTo(403));

        // 未通过绑定校验，不应签发 token
        verifyNoInteractions(jwtTokenService, sessionStore);
    }

    @Test
    void login_shouldUseRoleFromTenantBinding() {
        UserAccount user = buildUser();
        when(userRepository.findByUsername("nurse01")).thenReturn(user);
        when(userTenantRepository.findBinding(42L, TENANT)).thenReturn(binding("tenant_admin"));
        when(tenantPermissionRepository.findPermissions(anyString(), anyString()))
                .thenReturn(java.util.Set.of("system:user"));
        when(jwtTokenService.createToken(any(UserAccount.class), anyString(), anyString(), anyString()))
                .thenReturn("jwt-token");
        when(jwtTokenService.getTtl()).thenReturn(TOKEN_TTL);

        LoginResponse response = authService.login("nurse01", PASSWORD, TENANT);

        assertThat(response.getRole()).isEqualTo("tenant_admin");
    }

    @Test
    void login_shouldResolveTenantFromHeaderWhenRequestTenantMissing() {
        UserAccount user = buildUser();
        when(userRepository.findByUsername("nurse01")).thenReturn(user);
        when(userTenantRepository.findBinding(42L, TENANT)).thenReturn(binding("doctor"));
        when(tenantPermissionRepository.findPermissions(anyString(), anyString()))
                .thenReturn(java.util.Set.of("business:files"));
        when(jwtTokenService.createToken(any(UserAccount.class), anyString(), anyString(), anyString()))
                .thenReturn("jwt-token");
        when(jwtTokenService.getTtl()).thenReturn(TOKEN_TTL);

        // 请求体未传 tenantId，应回退到 TenantContext（X-Tenant-Id header）
        authService.login("nurse01", PASSWORD, null);

        verify(userTenantRepository).findBinding(42L, TENANT);
    }
}
