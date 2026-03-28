package com.waterinfo.platform.module.user.controller;

import com.waterinfo.platform.common.api.ApiResponse;
import com.waterinfo.platform.common.api.PageResponse;
import com.waterinfo.platform.module.user.dto.*;
import com.waterinfo.platform.module.user.service.UserService;
import com.waterinfo.platform.module.user.vo.UserVO;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

/**
 * User management controller
 */
@Tag(name = "用户管理", description = "用户管理相关接口")
@RestController
@RequestMapping("/api/v1/users")
@RequiredArgsConstructor
public class UserController {

    private final UserService userService;

    @Operation(summary = "创建用户", description = "创建新用户（仅 ADMIN）")
    @PostMapping
    @PreAuthorize("hasRole('ADMIN')")
    public ApiResponse<UserVO> createUser(@Valid @RequestBody CreateUserRequest request) {
        UserVO user = userService.createUser(request);
        return ApiResponse.success(user);
    }

    @Operation(summary = "根据ID获取用户", description = "根据用户ID获取用户详情")
    @GetMapping("/{id}")
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR')")
    public ApiResponse<UserVO> getUserById(@PathVariable String id) {
        UserVO user = userService.getUserById(id);
        return ApiResponse.success(user);
    }

    @Operation(summary = "查询用户", description = "按分页和筛选条件查询用户")
    @GetMapping
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR')")
    public ApiResponse<PageResponse<UserVO>> queryUsers(
            @RequestParam(defaultValue = "1") Integer page,
            @RequestParam(defaultValue = "20") Integer size,
            @RequestParam(required = false) String orgId,
            @RequestParam(required = false) String deptId,
            @RequestParam(required = false) String status,
            @RequestParam(required = false) String keyword) {
        
        com.waterinfo.platform.common.api.PageRequest pageRequest = new com.waterinfo.platform.common.api.PageRequest();
        pageRequest.setPage(page);
        pageRequest.setSize(size);
        
        var result = userService.queryUsers(pageRequest, orgId, deptId, status, keyword);
        return ApiResponse.success(PageResponse.of(result));
    }

    @Operation(summary = "更新用户", description = "更新用户信息（仅 ADMIN）")
    @PutMapping("/{id}")
    @PreAuthorize("hasRole('ADMIN')")
    public ApiResponse<UserVO> updateUser(@PathVariable String id, @Valid @RequestBody UpdateUserRequest request) {
        UserVO user = userService.updateUser(id, request);
        return ApiResponse.success(user);
    }

    @Operation(summary = "修改密码", description = "修改用户密码（ADMIN 可重置，用户可自改）")
    @PutMapping("/{id}/password")
    @PreAuthorize("hasRole('ADMIN') or #id == authentication.principal.id")
    public ApiResponse<Void> changePassword(@PathVariable String id, @Valid @RequestBody ChangePasswordRequest request) {
        boolean isAdmin = userService.getCurrentSecurityUser().getRoles().contains("ADMIN");
        userService.changePassword(id, request, isAdmin);
        return ApiResponse.success();
    }

    @Operation(summary = "设置用户角色", description = "为用户分配角色（仅 ADMIN）")
    @PutMapping("/{id}/roles")
    @PreAuthorize("hasRole('ADMIN')")
    public ApiResponse<Void> setUserRoles(@PathVariable String id, @Valid @RequestBody SetUserRolesRequest request) {
        userService.setUserRoles(id, request.getRoleIds());
        return ApiResponse.success();
    }

    @Operation(summary = "删除用户", description = "删除用户（逻辑删除，仅 ADMIN）")
    @DeleteMapping("/{id}")
    @PreAuthorize("hasRole('ADMIN')")
    public ApiResponse<Void> deleteUser(@PathVariable String id) {
        userService.deleteUser(id);
        return ApiResponse.success();
    }
}
