package com.waterinfo.platform.module.auth.controller;

import com.waterinfo.platform.common.api.ApiResponse;
import com.waterinfo.platform.module.auth.dto.LoginRequest;
import com.waterinfo.platform.module.auth.dto.LoginResponse;
import com.waterinfo.platform.module.auth.service.AuthService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

/**
 * Authentication controller
 */
@Tag(name = "认证鉴权", description = "认证相关接口")
@RestController
@RequestMapping("/api/v1/auth")
@RequiredArgsConstructor
public class AuthController {

    private final AuthService authService;

    @Operation(summary = "用户登录", description = "用户认证并获取 JWT 令牌")
    @PostMapping("/login")
    public ApiResponse<LoginResponse> login(@Valid @RequestBody LoginRequest request) {
        LoginResponse response = authService.login(request);
        return ApiResponse.success(response);
    }

    @Operation(summary = "获取当前用户", description = "获取当前已认证用户信息")
    @GetMapping("/me")
    public ApiResponse<LoginResponse.UserInfo> getCurrentUser() {
        LoginResponse.UserInfo userInfo = authService.getCurrentUser();
        return ApiResponse.success(userInfo);
    }

    @Operation(summary = "退出登录", description = "当前用户退出登录（客户端需自行丢弃令牌）")
    @PostMapping("/logout")
    public ApiResponse<Void> logout() {
        // JWT is stateless, client should discard the token
        // If implementing token blacklist, add logic here
        return ApiResponse.success();
    }
}
