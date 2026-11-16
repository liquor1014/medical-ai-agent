package com.medicalai.common;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * 租户用户与角色管理接口
 * 权限由 AuthorizationInterceptor 统一校验（system:user）
 */
@RestController
@RequestMapping("/api/admin/users")
@RequiredArgsConstructor
public class UserAdminController {

    private final RoleService roleService;

    /**
     * 列出指定租户下的全部用户及其角色
     * super_admin 可通过 tenantId 参数跨租户查看；tenant_admin 仅能查看本租户
     */
    @GetMapping
    public Result<List<Map<String, Object>>> list(
            @RequestParam(value = "tenantId", required = false) String tenantId) {
        return Result.success(roleService.listTenantUsers(tenantId));
    }

    /**
     * 为用户在指定租户下分配 / 修改角色
     */
    @PostMapping("/role")
    public Result<Void> assignRole(@RequestBody AssignRoleRequest req) {
        roleService.assignRole(req.getUserId(), req.getTenantId(), req.getRole());
        return Result.success();
    }

    /**
     * 解除用户与租户的绑定
     */
    @DeleteMapping
    public Result<Void> unbind(@RequestParam Long userId,
                               @RequestParam(value = "tenantId", required = false) String tenantId) {
        roleService.unbindUser(userId, tenantId);
        return Result.success();
    }

    @Data
    public static class AssignRoleRequest {
        @NotNull(message = "用户 ID 不能为空")
        private Long userId;

        private String tenantId;

        @NotBlank(message = "角色不能为空")
        private String role;
    }
}
