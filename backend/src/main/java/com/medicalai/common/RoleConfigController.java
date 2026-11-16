package com.medicalai.common;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 角色配置管理接口
 * 权限由 AuthorizationInterceptor 统一校验（/api/roles/** → system:role）
 */
@RestController
@RequestMapping("/api/roles")
@RequiredArgsConstructor
public class RoleConfigController {

    private final RoleConfigService roleConfigService;

    @GetMapping
    public Result<List<Role>> list() {
        return Result.success(roleConfigService.list());
    }

    @PostMapping
    public Result<Role> create(@RequestBody RoleRequest req) {
        Role role = new Role();
        role.setCode(req.getCode());
        role.setName(req.getName());
        role.setDescription(req.getDescription());
        return Result.success(roleConfigService.create(role));
    }

    @PutMapping("/{code}")
    public Result<Role> update(@PathVariable String code, @RequestBody RoleRequest req) {
        Role role = new Role();
        role.setName(req.getName());
        role.setDescription(req.getDescription());
        return Result.success(roleConfigService.update(code, role));
    }

    @DeleteMapping("/{code}")
    public Result<Void> delete(@PathVariable String code) {
        roleConfigService.delete(code);
        return Result.success();
    }

    @PatchMapping("/{code}/status")
    public Result<Role> toggleStatus(@PathVariable String code, @RequestBody StatusRequest req) {
        return Result.success(roleConfigService.toggleStatus(code, req.getStatus()));
    }

    @Data
    public static class RoleRequest {
        private String code;
        @NotBlank(message = "角色名称不能为空")
        private String name;
        private String description;
    }

    @Data
    public static class StatusRequest {
        @NotBlank(message = "状态不能为空")
        private String status;
    }
}
