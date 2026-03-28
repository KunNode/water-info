package com.waterinfo.platform.module.user.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.waterinfo.platform.common.api.ApiResponse;
import com.waterinfo.platform.common.api.PageRequest;
import com.waterinfo.platform.common.api.PageResponse;
import com.waterinfo.platform.common.exception.BusinessException;
import com.waterinfo.platform.common.exception.ErrorCode;
import com.waterinfo.platform.module.user.entity.SysRole;
import com.waterinfo.platform.module.user.mapper.SysRoleMapper;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * Role management controller
 */
@Tag(name = "角色管理", description = "角色管理相关接口")
@RestController
@RequestMapping("/api/v1/roles")
@RequiredArgsConstructor
public class RoleController {

    private final SysRoleMapper roleMapper;

    @Operation(summary = "查询角色列表", description = "分页查询全部角色")
    @GetMapping
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR')")
    public ApiResponse<PageResponse<SysRole>> getRoles(
            @RequestParam(defaultValue = "1") Integer page,
            @RequestParam(defaultValue = "20") Integer size) {
        
        Page<SysRole> pageObj = new Page<>(page, size);
        Page<SysRole> result = roleMapper.selectPage(pageObj, 
                new LambdaQueryWrapper<SysRole>().orderByAsc(SysRole::getCode));
        
        return ApiResponse.success(PageResponse.of(result));
    }

    @Operation(summary = "根据ID获取角色", description = "根据角色ID获取角色详情")
    @GetMapping("/{id}")
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR')")
    public ApiResponse<SysRole> getRoleById(@PathVariable String id) {
        SysRole role = roleMapper.selectById(id);
        if (role == null) {
            throw new BusinessException(ErrorCode.USER_ROLE_NOT_FOUND);
        }
        return ApiResponse.success(role);
    }
}
