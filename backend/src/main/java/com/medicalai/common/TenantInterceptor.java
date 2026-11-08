package com.medicalai.common;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.HandlerInterceptor;

/**
 * 租户拦截器：从请求头提取 tenant_id 写入上下文
 */
@Slf4j
@Component
public class TenantInterceptor implements HandlerInterceptor {

    @Value("${app.tenant.header:X-Tenant-Id}")
    private String tenantHeader;

    @Value("${app.tenant.default-tenant:hospital-demo}")
    private String defaultTenant;

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) {
        String tenantId = request.getHeader(tenantHeader);
        if (tenantId == null || tenantId.isBlank()) {
            tenantId = defaultTenant;
        }
        TenantContext.setTenantId(tenantId);
        log.debug("当前租户: {}", tenantId);
        return true;
    }

    @Override
    public void afterCompletion(HttpServletRequest request, HttpServletResponse response, Object handler, Exception ex) {
        TenantContext.clear();
    }
}
