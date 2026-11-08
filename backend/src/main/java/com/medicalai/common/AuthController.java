package com.medicalai.common;

import com.medicalai.common.dto.LoginRequest;
import com.medicalai.common.dto.LoginResponse;
import com.medicalai.common.dto.RegisterRequest;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

/**
 * 认证接口
 */
@RestController
@RequestMapping("/api/auth")
@RequiredArgsConstructor
public class AuthController {

    private final AuthService authService;

    @PostMapping("/login")
    public Result<LoginResponse> login(@Valid @RequestBody LoginRequest req) {
        String token = authService.login(req.getUsername(), req.getPassword());
        return Result.success(new LoginResponse(token, req.getUsername()));
    }

    @PostMapping("/register")
    public Result<LoginResponse> register(@Valid @RequestBody RegisterRequest req) {
        String username = req.getUsername().trim();
        String token = authService.register(username, req.getPassword(), req.getDisplayName());
        return Result.success(new LoginResponse(token, username));
    }

    @PostMapping("/logout")
    public Result<Void> logout(HttpServletRequest request) {
        String token = request.getHeader("Authorization");
        if (token != null && token.startsWith("Bearer ")) {
            token = token.substring(7);
        }
        authService.logout(token);
        return Result.success();
    }

    @GetMapping("/me")
    public Result<String> me() {
        return Result.success(UserContext.getUsername());
    }
}
