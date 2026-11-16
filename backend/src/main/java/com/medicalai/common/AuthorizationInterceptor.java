package com.medicalai.common;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.HandlerInterceptor;

/**
 * 全局授权拦截器：在认证拦截器之后执行，统一校验当前用户对请求路径的访问权限
 * 避免权限校验逻辑散落在各 Controller / Service 中
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class AuthorizationInterceptor implements HandlerInterceptor {

    private final AuthorizationService authorizationService;

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) throws Exception {
        String uri = request.getRequestURI();
        String permission = authorizationService.resolvePermission(uri);
        if (!authorizationService.hasPermission(permission)) {
            log.warn("权限不足: user={}, role={}, tenant={}, uri={}, required={}",
                    UserContext.getUsername(), UserContext.getRole(), TenantContext.getTenantId(), uri, permission);
            writeError(response, 403, "无权限访问该资源");
            return false;
        }
        return true;
    }

    private void writeError(HttpServletResponse response, int code, String message) throws Exception {
        response.setStatus(code);
        response.setContentType("application/json;charset=UTF-8");
        response.getWriter().write("{\"code\":" + code + ",\"message\":\"" + message + "\"}");
    }
}
