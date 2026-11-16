package com.medicalai.config;

import com.medicalai.common.AuthInterceptor;
import com.medicalai.common.AuthorizationInterceptor;
import com.medicalai.common.TenantInterceptor;
import lombok.RequiredArgsConstructor;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

/**
 * Web 配置：CORS + 拦截器
 */
@Configuration
@RequiredArgsConstructor
public class WebConfig implements WebMvcConfigurer {

    private final TenantInterceptor tenantInterceptor;
    private final AuthInterceptor authInterceptor;
    private final AuthorizationInterceptor authorizationInterceptor;

    @Override
    public void addCorsMappings(CorsRegistry registry) {
        registry.addMapping("/**")
                .allowedOriginPatterns("*")
                .allowedMethods("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS")
                .allowedHeaders("*")
                .allowCredentials(true)
                .maxAge(3600);
    }

    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        // 租户拦截器（所有请求；登录也需要租户上下文来定位用户）
        registry.addInterceptor(tenantInterceptor)
                .addPathPatterns("/**")
                .excludePathPatterns("/actuator/**");

        // 认证拦截器（登录/注册/密码找回/租户公开列表无需 token）
        registry.addInterceptor(authInterceptor)
                .addPathPatterns("/**")
                .excludePathPatterns("/actuator/**",
                        "/api/auth/login",
                        "/api/auth/register",
                        "/api/auth/password/policy",
                        "/api/auth/password/forgot-code",
                        "/api/auth/password/verify-code",
                        "/api/auth/password/reset",
                        "/api/tenants/list");

        // 授权拦截器（在认证之后执行，统一校验权限；排除无需登录的路径）
        registry.addInterceptor(authorizationInterceptor)
                .addPathPatterns("/**")
                .excludePathPatterns("/actuator/**",
                        "/api/auth/login",
                        "/api/auth/register",
                        "/api/auth/password/policy",
                        "/api/auth/password/forgot-code",
                        "/api/auth/password/verify-code",
                        "/api/auth/password/reset",
                        "/api/tenants/list");
    }
}
