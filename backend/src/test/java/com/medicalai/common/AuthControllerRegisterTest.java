package com.medicalai.common;

import com.medicalai.common.dto.LoginResponse;
import com.medicalai.common.dto.RegisterRequest;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * 注册接口单元测试（AuthController）
 */
class AuthControllerRegisterTest {

    private AuthService authService;
    private AuthController authController;

    @BeforeEach
    void setUp() {
        authService = mock(AuthService.class);
        authController = new AuthController(authService);
    }

    private RegisterRequest request(String username, String password, String displayName) {
        RegisterRequest req = new RegisterRequest();
        req.setUsername(username);
        req.setPassword(password);
        req.setDisplayName(displayName);
        return req;
    }

    @Test
    void register_shouldTrimUsernameAndReturnLoginResponse() {
        when(authService.register("nurse01", "nurse123", "护士小王")).thenReturn("jwt-token");

        Result<LoginResponse> result = authController.register(request("  nurse01  ", "nurse123", "护士小王"));

        assertThat(result.getCode()).isEqualTo(200);
        assertThat(result.getData().getToken()).isEqualTo("jwt-token");
        assertThat(result.getData().getUsername()).isEqualTo("nurse01");
        verify(authService).register("nurse01", "nurse123", "护士小王");
    }

    @Test
    void register_shouldAllowMissingDisplayName() {
        when(authService.register("nurse02", "nurse123", null)).thenReturn("jwt-token");

        Result<LoginResponse> result = authController.register(request("nurse02", "nurse123", null));

        assertThat(result.getData().getUsername()).isEqualTo("nurse02");
        verify(authService).register("nurse02", "nurse123", null);
    }

    @Test
    void register_shouldPropagateBusinessException() {
        when(authService.register("admin", "nurse123", null))
                .thenThrow(new BusinessException(409, "用户名已存在"));

        assertThatThrownBy(() -> authController.register(request("admin", "nurse123", null)))
                .isInstanceOf(BusinessException.class)
                .hasMessage("用户名已存在")
                .satisfies(e -> assertThat(((BusinessException) e).getCode()).isEqualTo(409));
    }
}
