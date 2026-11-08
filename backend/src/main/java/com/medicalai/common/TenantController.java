package com.medicalai.common;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

/**
 * 租户接口
 */
@RestController
@RequestMapping("/api/tenants")
public class TenantController {

    @GetMapping("/current")
    public Result<Map<String, String>> current() {
        return Result.success(Map.of(
                "tenantId", TenantContext.getTenantId(),
                "username", UserContext.getUsername()
        ));
    }

    @GetMapping("/list")
    public Result<List<Map<String, String>>> list() {
        List<Map<String, String>> tenants = List.of(
                Map.of("id", "hospital-demo", "name", "演示院区"),
                Map.of("id", "hospital-a", "name", "A 院区"),
                Map.of("id", "hospital-b", "name", "B 院区")
        );
        return Result.success(tenants);
    }
}
