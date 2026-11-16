package com.medicalai.common.dto;

import lombok.AllArgsConstructor;
import lombok.Data;

import java.util.List;

@Data
@AllArgsConstructor
public class LoginResponse {
    private String token;
    private String username;
    private String tenantId;
    private String role;
    private String displayName;
    private List<String> permissions;
}
