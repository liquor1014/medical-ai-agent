package com.medicalai.common;

import com.medicalai.common.dto.LoginResponse;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.util.ReflectionTestUtils;

import java.time.Duration;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.lenient;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

/**
 * 注册功能单元测试（AuthService）
 */
@ExtendWith(MockitoExtension.class)
class AuthServiceRegisterTest {

    private static final String TENANT = "hospital-demo";
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
        lenient().when(tenantPermissionRepository.findPermissions(anyString(), anyString()))
                .thenReturn(java.util.Set.of());
    }

    @AfterEach
    void tearDown() {
        TenantContext.clear();
        UserContext.clear();
    }

    @Test
    void register_shouldSaveBcryptUserAndCreateSession() {
        when(userRepository.findByUsername("nurse01")).thenReturn(null);
        when(userRepository.insert(any(UserAccount.class))).thenReturn(100L);
        when(jwtTokenService.createToken(any(UserAccount.class), anyString(), anyString(), anyString()))
                .thenReturn("jwt-token");
        when(jwtTokenService.getTtl()).thenReturn(TOKEN_TTL);

        LoginResponse response = authService.register("nurse01", PASSWORD, null, "Nurse01@Example.com", null);

        assertThat(response.getToken()).isEqualTo("jwt-token");
        assertThat(response.getUsername()).isEqualTo("nurse01");
        assertThat(response.getTenantId()).isEqualTo(TENANT);
        assertThat(response.getRole()).isEqualTo("doctor");

        ArgumentCaptor<UserAccount> userCaptor = ArgumentCaptor.forClass(UserAccount.class);
        verify(userRepository).insert(userCaptor.capture());
        UserAccount saved = userCaptor.getValue();
        assertThat(saved.getTenantId()).isEqualTo(TENANT);
        assertThat(saved.getUsername()).isEqualTo("nurse01");
        assertThat(saved.getRole()).isEqualTo("doctor");
        assertThat(saved.getStatus()).isEqualTo("active");
        assertThat(saved.getDisplayName()).isEqualTo("nurse01");
        assertThat(saved.getEmail()).isEqualTo("nurse01@example.com");
        assertThat(saved.getPasswordHash()).isNotEqualTo(PASSWORD);
        assertThat(passwordEncoder.matches(PASSWORD, saved.getPasswordHash())).isTrue();

        // 注册后应自动建立用户与租户的绑定关系
        ArgumentCaptor<UserTenant> bindingCaptor = ArgumentCaptor.forClass(UserTenant.class);
        verify(userTenantRepository).insert(bindingCaptor.capture());
        UserTenant binding = bindingCaptor.getValue();
        assertThat(binding.getUserId()).isEqualTo(100L);
        assertThat(binding.getTenantId()).isEqualTo(TENANT);
        assertThat(binding.getRole()).isEqualTo("doctor");

        // JWT 的 jti 必须与 Redis 会话 key 一致，登出时才能准确吊销
        ArgumentCaptor<String> jtiCaptor = ArgumentCaptor.forClass(String.class);
        verify(jwtTokenService).createToken(any(UserAccount.class), anyString(), anyString(), jtiCaptor.capture());
        verify(sessionStore).save(eq(jtiCaptor.getValue()), eq(TENANT), eq("nurse01"), eq(TOKEN_TTL));
    }

    @Test
    void register_shouldRejectWeakPassword() {
        assertThatThrownBy(() -> authService.register("nurse06", "nurse123", null, null, null))
                .isInstanceOf(BusinessException.class)
                .hasMessageContaining("至少 3 类")
                .satisfies(e -> assertThat(((BusinessException) e).getCode()).isEqualTo(400));
        verifyNoInteractions(userRepository, jwtTokenService, sessionStore, userTenantRepository);
    }

    @Test
    void register_shouldTrimDisplayName() {
        when(userRepository.findByUsername("nurse02")).thenReturn(null);
        when(userRepository.insert(any(UserAccount.class))).thenReturn(101L);
        when(jwtTokenService.createToken(any(UserAccount.class), anyString(), anyString(), anyString()))
                .thenReturn("jwt-token");
        when(jwtTokenService.getTtl()).thenReturn(TOKEN_TTL);

        authService.register("nurse02", PASSWORD, "  护士小王  ", null, null);

        ArgumentCaptor<UserAccount> captor = ArgumentCaptor.forClass(UserAccount.class);
        verify(userRepository).insert(captor.capture());
        assertThat(captor.getValue().getDisplayName()).isEqualTo("护士小王");
    }

    @Test
    void register_shouldFallbackToUsernameWhenDisplayNameBlank() {
        when(userRepository.findByUsername("nurse03")).thenReturn(null);
        when(userRepository.insert(any(UserAccount.class))).thenReturn(102L);
        when(jwtTokenService.createToken(any(UserAccount.class), anyString(), anyString(), anyString()))
                .thenReturn("jwt-token");
        when(jwtTokenService.getTtl()).thenReturn(TOKEN_TTL);

        authService.register("nurse03", PASSWORD, "   ", null, null);

        ArgumentCaptor<UserAccount> captor = ArgumentCaptor.forClass(UserAccount.class);
        verify(userRepository).insert(captor.capture());
        assertThat(captor.getValue().getDisplayName()).isEqualTo("nurse03");
    }

    @Test
    void register_shouldRejectDuplicateUsername() {
        UserAccount existing = new UserAccount();
        existing.setUsername("nurse01");
        when(userRepository.findByUsername("nurse01")).thenReturn(existing);

        assertThatThrownBy(() -> authService.register("nurse01", PASSWORD, null, null, null))
                .isInstanceOf(BusinessException.class)
                .hasMessage("用户名已存在")
                .satisfies(e -> assertThat(((BusinessException) e).getCode()).isEqualTo(409));

        verify(userRepository, never()).insert(any(UserAccount.class));
        verifyNoInteractions(jwtTokenService, sessionStore, userTenantRepository);
    }

    @Test
    void register_shouldRejectDuplicateUsernameOnInsertConflict() {
        when(userRepository.findByUsername("nurse01")).thenReturn(null);
        doThrow(new DuplicateKeyException("duplicate key")).when(userRepository).insert(any(UserAccount.class));

        assertThatThrownBy(() -> authService.register("nurse01", PASSWORD, null, null, null))
                .isInstanceOf(BusinessException.class)
                .hasMessage("用户名已存在")
                .satisfies(e -> assertThat(((BusinessException) e).getCode()).isEqualTo(409));

        verifyNoInteractions(jwtTokenService, sessionStore, userTenantRepository);
    }

    @Test
    void register_shouldUseTenantFromContextWhenRequestTenantMissing() {
        TenantContext.setTenantId("hospital-a");
        when(userRepository.findByUsername("nurse04")).thenReturn(null);
        when(userRepository.insert(any(UserAccount.class))).thenReturn(104L);
        when(jwtTokenService.createToken(any(UserAccount.class), anyString(), anyString(), anyString()))
                .thenReturn("jwt-token");
        when(jwtTokenService.getTtl()).thenReturn(TOKEN_TTL);

        authService.register("nurse04", PASSWORD, null, null, null);

        ArgumentCaptor<UserAccount> captor = ArgumentCaptor.forClass(UserAccount.class);
        verify(userRepository).insert(captor.capture());
        assertThat(captor.getValue().getTenantId()).isEqualTo("hospital-a");
    }

    @Test
    void register_shouldUseExplicitRequestTenantId() {
        when(userRepository.findByUsername("nurse07")).thenReturn(null);
        when(userRepository.insert(any(UserAccount.class))).thenReturn(107L);
        when(jwtTokenService.createToken(any(UserAccount.class), anyString(), anyString(), anyString()))
                .thenReturn("jwt-token");
        when(jwtTokenService.getTtl()).thenReturn(TOKEN_TTL);

        authService.register("nurse07", PASSWORD, null, null, "hospital-b");

        ArgumentCaptor<UserAccount> captor = ArgumentCaptor.forClass(UserAccount.class);
        verify(userRepository).insert(captor.capture());
        assertThat(captor.getValue().getTenantId()).isEqualTo("hospital-b");

        ArgumentCaptor<UserTenant> bindingCaptor = ArgumentCaptor.forClass(UserTenant.class);
        verify(userTenantRepository).insert(bindingCaptor.capture());
        assertThat(bindingCaptor.getValue().getTenantId()).isEqualTo("hospital-b");
    }

    @Test
    void register_shouldFallbackToDefaultTenantWhenContextMissing() {
        TenantContext.clear();
        when(userRepository.findByUsername("nurse05")).thenReturn(null);
        when(userRepository.insert(any(UserAccount.class))).thenReturn(105L);
        when(jwtTokenService.createToken(any(UserAccount.class), anyString(), anyString(), anyString()))
                .thenReturn("jwt-token");
        when(jwtTokenService.getTtl()).thenReturn(TOKEN_TTL);

        authService.register("nurse05", PASSWORD, null, null, null);

        ArgumentCaptor<UserAccount> captor = ArgumentCaptor.forClass(UserAccount.class);
        verify(userRepository).insert(captor.capture());
        assertThat(captor.getValue().getTenantId()).isEqualTo(TENANT);
    }
}
