package com.medicalai.common;

import com.medicalai.common.dto.TenantRequest;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * 租户接口：登录页动态列表（公开）+ 管理员维护（admin 鉴权）
 */
@RestController
@RequestMapping("/api/tenants")
@RequiredArgsConstructor
public class TenantController {

    private final TenantService tenantService;

    @GetMapping("/current")
    public Result<Map<String, String>> current() {
        return Result.success(Map.of(
                "tenantId", TenantContext.getTenantId(),
                "username", UserContext.getUsername(),
                "role", UserContext.getRole() == null ? "" : UserContext.getRole()
        ));
    }

    /**
     * 登录页租户下拉列表（仅启用租户，无需登录）
     */
    @GetMapping("/list")
    public Result<List<Map<String, String>>> list() {
        List<Map<String, String>> tenants = tenantService.listActive().stream()
                .map(t -> Map.of("id", t.getId(), "name", t.getName()))
                .toList();
        return Result.success(tenants);
    }

    /**
     * 管理端租户列表（含禁用租户与用户数）
     */
    @GetMapping("/admin/list")
    public Result<List<Tenant>> adminList() {
        return Result.success(tenantService.listAll());
    }

    @PostMapping("/admin")
    public Result<Tenant> create(@Valid @RequestBody TenantRequest req) {
        return Result.success(tenantService.create(toTenant(req)));
    }

    @PutMapping("/admin/{id}")
    public Result<Tenant> update(@PathVariable String id, @Valid @RequestBody TenantRequest req) {
        return Result.success(tenantService.update(id, toTenant(req)));
    }

    @DeleteMapping("/admin/{id}")
    public Result<Void> delete(@PathVariable String id) {
        tenantService.delete(id);
        return Result.success();
    }

    private Tenant toTenant(TenantRequest req) {
        Tenant tenant = new Tenant();
        tenant.setId(req.getId());
        tenant.setName(req.getName());
        tenant.setDescription(req.getDescription());
        tenant.setStatus(req.getStatus() == null ? "active" : req.getStatus());
        tenant.setSortOrder(req.getSortOrder() == null ? 0 : req.getSortOrder());
        return tenant;
    }
}
