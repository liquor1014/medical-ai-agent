package com.medicalai.common.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Data;

/**
 * 租户新增 / 编辑请求
 */
@Data
public class TenantRequest {

    @Size(max = 64, message = "租户 ID 长度不能超过 64 位")
    private String id;

    @NotBlank(message = "租户名称不能为空")
    @Size(max = 128, message = "租户名称长度不能超过 128 位")
    private String name;

    @Size(max = 255, message = "租户描述长度不能超过 255 位")
    private String description;

    private String status;

    private Integer sortOrder;
}
