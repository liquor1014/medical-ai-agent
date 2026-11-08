package com.medicalai.common;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.HandlerInterceptor;

/**
 * 认证拦截器：校验 JWT 签名/有效期，并确认 Redis 会话仍然有效（支持登出吊销）
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class AuthInterceptor implements HandlerInterceptor {

    private final AuthService authService;

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) throws Exception {
        String token = request.getHeader("Authorization");
        if (token != null && token.startsWith("Bearer ")) {
            token = token.substring(7);
        }

        if (token == null || token.isBlank()) {
            writeError(response, 401, "未登录或 Token 缺失");
            return false;
        }

        JwtTokenService.TokenPayload payload = authService.verify(token);
        if (payload == null) {
            writeError(response, 401, "Token 无效或已过期");
            return false;
        }

        UserContext.setUsername(payload.username());
        // 以 Token 内的租户为准，避免通过请求头越权访问其他租户数据
        TenantContext.setTenantId(payload.tenantId());
        log.debug("认证通过: {} (tenant={})", payload.username(), payload.tenantId());
        return true;
    }

    private void writeError(HttpServletResponse response, int code, String message) throws Exception {
        response.setStatus(code);
        response.setContentType("application/json;charset=UTF-8");
        response.getWriter().write("{\"code\":" + code + ",\"message\":\"" + message + "\"}");
    }

    @Override
    public void afterCompletion(HttpServletRequest request, HttpServletResponse response, Object handler, Exception ex) {
        UserContext.clear();
    }
}
