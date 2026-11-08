package com.medicalai.common;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.test.util.ReflectionTestUtils;

import java.time.Duration;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.doThrow;
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
    private static final Duration TOKEN_TTL = Duration.ofHours(12);

    @Mock
    private UserRepository userRepository;

    @Mock
    private JwtTokenService jwtTokenService;

    @Mock
    private SessionStore sessionStore;

    private AuthService authService;

    @BeforeEach
    void setUp() {
        authService = new AuthService(userRepository, jwtTokenService, sessionStore);
        ReflectionTestUtils.setField(authService, "defaultTenant", TENANT);
        TenantContext.setTenantId(TENANT);
    }

    @AfterEach
    void tearDown() {
        TenantContext.clear();
    }

    @Test
    void register_shouldSaveBcryptUserAndCreateSession() {
        when(userRepository.findByTenantAndUsername(TENANT, "nurse01")).thenReturn(null);
        when(jwtTokenService.createToken(any(UserAccount.class), anyString())).thenReturn("jwt-token");
        when(jwtTokenService.getTtl()).thenReturn(TOKEN_TTL);

        String token = authService.register("nurse01", "nurse123", null);

        assertThat(token).isEqualTo("jwt-token");

        ArgumentCaptor<UserAccount> userCaptor = ArgumentCaptor.forClass(UserAccount.class);
        verify(userRepository).insert(userCaptor.capture());
        UserAccount saved = userCaptor.getValue();
        assertThat(saved.getTenantId()).isEqualTo(TENANT);
        assertThat(saved.getUsername()).isEqualTo("nurse01");
        assertThat(saved.getRole()).isEqualTo("doctor");
        assertThat(saved.getStatus()).isEqualTo("active");
        assertThat(saved.getDisplayName()).isEqualTo("nurse01");
        assertThat(saved.getPasswordHash()).isNotEqualTo("nurse123");
        assertThat(new BCryptPasswordEncoder().matches("nurse123", saved.getPasswordHash())).isTrue();

        // JWT 的 jti 必须与 Redis 会话 key 一致，登出时才能准确吊销
        ArgumentCaptor<String> jtiCaptor = ArgumentCaptor.forClass(String.class);
        verify(jwtTokenService).createToken(any(UserAccount.class), jtiCaptor.capture());
        verify(sessionStore).save(eq(jtiCaptor.getValue()), eq("nurse01"), eq(TOKEN_TTL));
    }

    @Test
    void register_shouldTrimDisplayName() {
        when(userRepository.findByTenantAndUsername(TENANT, "nurse02")).thenReturn(null);
        when(jwtTokenService.createToken(any(UserAccount.class), anyString())).thenReturn("jwt-token");
        when(jwtTokenService.getTtl()).thenReturn(TOKEN_TTL);

        authService.register("nurse02", "nurse123", "  护士小王  ");

        ArgumentCaptor<UserAccount> captor = ArgumentCaptor.forClass(UserAccount.class);
        verify(userRepository).insert(captor.capture());
        assertThat(captor.getValue().getDisplayName()).isEqualTo("护士小王");
    }

    @Test
    void register_shouldFallbackToUsernameWhenDisplayNameBlank() {
        when(userRepository.findByTenantAndUsername(TENANT, "nurse03")).thenReturn(null);
        when(jwtTokenService.createToken(any(UserAccount.class), anyString())).thenReturn("jwt-token");
        when(jwtTokenService.getTtl()).thenReturn(TOKEN_TTL);

        authService.register("nurse03", "nurse123", "   ");

        ArgumentCaptor<UserAccount> captor = ArgumentCaptor.forClass(UserAccount.class);
        verify(userRepository).insert(captor.capture());
        assertThat(captor.getValue().getDisplayName()).isEqualTo("nurse03");
    }

    @Test
    void register_shouldRejectDuplicateUsername() {
        UserAccount existing = new UserAccount();
        existing.setUsername("nurse01");
        when(userRepository.findByTenantAndUsername(TENANT, "nurse01")).thenReturn(existing);

        assertThatThrownBy(() -> authService.register("nurse01", "nurse123", null))
                .isInstanceOf(BusinessException.class)
                .hasMessage("用户名已存在")
                .satisfies(e -> assertThat(((BusinessException) e).getCode()).isEqualTo(409));

        verify(userRepository, never()).insert(any(UserAccount.class));
        verifyNoInteractions(jwtTokenService, sessionStore);
    }

    @Test
    void register_shouldRejectDuplicateUsernameOnInsertConflict() {
        when(userRepository.findByTenantAndUsername(TENANT, "nurse01")).thenReturn(null);
        doThrow(new DuplicateKeyException("duplicate key")).when(userRepository).insert(any(UserAccount.class));

        assertThatThrownBy(() -> authService.register("nurse01", "nurse123", null))
                .isInstanceOf(BusinessException.class)
                .hasMessage("用户名已存在")
                .satisfies(e -> assertThat(((BusinessException) e).getCode()).isEqualTo(409));

        verifyNoInteractions(jwtTokenService, sessionStore);
    }

    @Test
    void register_shouldUseTenantFromContext() {
        TenantContext.setTenantId("hospital-a");
        when(userRepository.findByTenantAndUsername("hospital-a", "nurse04")).thenReturn(null);
        when(jwtTokenService.createToken(any(UserAccount.class), anyString())).thenReturn("jwt-token");
        when(jwtTokenService.getTtl()).thenReturn(TOKEN_TTL);

        authService.register("nurse04", "nurse123", null);

        ArgumentCaptor<UserAccount> captor = ArgumentCaptor.forClass(UserAccount.class);
        verify(userRepository).insert(captor.capture());
        assertThat(captor.getValue().getTenantId()).isEqualTo("hospital-a");
    }

    @Test
    void register_shouldFallbackToDefaultTenantWhenContextMissing() {
        TenantContext.clear();
        when(userRepository.findByTenantAndUsername(TENANT, "nurse05")).thenReturn(null);
        when(jwtTokenService.createToken(any(UserAccount.class), anyString())).thenReturn("jwt-token");
        when(jwtTokenService.getTtl()).thenReturn(TOKEN_TTL);

        authService.register("nurse05", "nurse123", null);

        ArgumentCaptor<UserAccount> captor = ArgumentCaptor.forClass(UserAccount.class);
        verify(userRepository).insert(captor.capture());
        assertThat(captor.getValue().getTenantId()).isEqualTo(TENANT);
    }
}
