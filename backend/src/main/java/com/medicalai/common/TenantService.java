package com.medicalai.common;

import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * 租户管理：登录页动态列表 + 管理员维护（新增 / 编辑 / 启停 / 删除）
 */
@Service
@RequiredArgsConstructor
public class TenantService {

    private final TenantRepository tenantRepository;

    @Value("${app.tenant.default-tenant:hospital-demo}")
    private String defaultTenant;

    /**
     * 登录页可用的租户（启用状态）
     */
    public List<Tenant> listActive() {
        return tenantRepository.findAll(true);
    }

    /**
     * 管理端列表（含禁用租户与用户数）
     */
    public List<Tenant> listAll() {
        UserContext.requireSuperAdmin();
        return tenantRepository.findAll(false);
    }

    public Tenant create(Tenant tenant) {
        UserContext.requireSuperAdmin();
        String id = tenant.getId() == null ? "" : tenant.getId().trim();
        if (id.isEmpty()) {
            throw new BusinessException(400, "租户 ID 不能为空");
        }
        if (!id.matches("^[a-z0-9][a-z0-9-]{1,62}$")) {
            throw new BusinessException(400, "租户 ID 需为 2-63 位小写字母、数字或中划线，且以字母或数字开头");
        }
        if (tenantRepository.findById(id) != null) {
            throw new BusinessException(409, "租户 ID 已存在");
        }
        tenant.setId(id);
        normalize(tenant);
        tenantRepository.insert(tenant);
        return tenantRepository.findById(id);
    }

    public Tenant update(String id, Tenant tenant) {
        UserContext.requireSuperAdmin();
        Tenant existing = tenantRepository.findById(id);
        if (existing == null) {
            throw new BusinessException(404, "租户不存在");
        }
        tenant.setId(id);
        normalize(tenant);
        if (id.equals(defaultTenant) && "disabled".equals(tenant.getStatus())) {
            throw new BusinessException(400, "默认演示租户不允许禁用");
        }
        tenantRepository.update(tenant);
        return tenantRepository.findById(id);
    }

    public void delete(String id) {
        UserContext.requireSuperAdmin();
        Tenant existing = tenantRepository.findById(id);
        if (existing == null) {
            throw new BusinessException(404, "租户不存在");
        }
        if (id.equals(defaultTenant)) {
            throw new BusinessException(400, "默认演示租户不允许删除");
        }
        int users = tenantRepository.countUsers(id);
        if (users > 0) {
            throw new BusinessException(409, "该租户下仍有 " + users + " 个用户，无法删除");
        }
        tenantRepository.delete(id);
    }

    private void normalize(Tenant tenant) {
        tenant.setName(tenant.getName() == null ? "" : tenant.getName().trim());
        if (tenant.getName().isEmpty()) {
            throw new BusinessException(400, "租户名称不能为空");
        }
        String status = tenant.getStatus() == null ? "active" : tenant.getStatus().trim().toLowerCase();
        if (!"active".equals(status) && !"disabled".equals(status)) {
            throw new BusinessException(400, "租户状态仅支持 active / disabled");
        }
        tenant.setStatus(status);
        tenant.setDescription(tenant.getDescription() == null ? null : tenant.getDescription().trim());
        if (tenant.getSortOrder() < 0) {
            tenant.setSortOrder(0);
        }
    }
}
