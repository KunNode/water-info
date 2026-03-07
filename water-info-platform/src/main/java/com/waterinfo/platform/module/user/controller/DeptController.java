package com.waterinfo.platform.module.user.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.waterinfo.platform.common.api.ApiResponse;
import com.waterinfo.platform.common.api.PageResponse;
import com.waterinfo.platform.common.exception.BusinessException;
import com.waterinfo.platform.common.exception.ErrorCode;
import com.waterinfo.platform.module.user.entity.SysDept;
import com.waterinfo.platform.module.user.mapper.SysDeptMapper;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.util.StringUtils;
import org.springframework.web.bind.annotation.*;

/**
 * Department management controller
 */
@Tag(name = "部门管理", description = "部门管理相关接口")
@RestController
@RequestMapping("/api/v1/depts")
@RequiredArgsConstructor
public class DeptController {

    private final SysDeptMapper deptMapper;

    @Data
    public static class CreateDeptRequest {
        @NotBlank(message = "Organization ID is required")
        private String orgId;
        @NotBlank(message = "Name is required")
        private String name;
        private String parentId;
    }

    @Data
    public static class UpdateDeptRequest {
        private String name;
        private String parentId;
    }

    @Operation(summary = "创建部门", description = "创建新部门")
    @PostMapping
    @PreAuthorize("hasRole('ADMIN')")
    public ApiResponse<SysDept> createDept(@Valid @RequestBody CreateDeptRequest request) {
        SysDept dept = SysDept.builder()
                .orgId(request.getOrgId())
                .name(request.getName())
                .parentId(request.getParentId())
                .build();
        deptMapper.insert(dept);
        return ApiResponse.success(dept);
    }

    @Operation(summary = "查询部门列表", description = "分页查询部门列表")
    @GetMapping
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR', 'VIEWER')")
    public ApiResponse<PageResponse<SysDept>> getDepts(
            @RequestParam(defaultValue = "1") Integer page,
            @RequestParam(defaultValue = "20") Integer size,
            @RequestParam(required = false) String orgId) {
        
        Page<SysDept> pageObj = new Page<>(page, size);
        LambdaQueryWrapper<SysDept> wrapper = new LambdaQueryWrapper<>();
        
        if (StringUtils.hasText(orgId)) {
            wrapper.eq(SysDept::getOrgId, orgId);
        }
        wrapper.orderByAsc(SysDept::getName);
        
        Page<SysDept> result = deptMapper.selectPage(pageObj, wrapper);
        return ApiResponse.success(PageResponse.of(result));
    }

    @Operation(summary = "根据ID获取部门", description = "根据部门ID获取部门详情")
    @GetMapping("/{id}")
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR', 'VIEWER')")
    public ApiResponse<SysDept> getDeptById(@PathVariable String id) {
        SysDept dept = deptMapper.selectById(id);
        if (dept == null) {
            throw new BusinessException(ErrorCode.DEPT_NOT_FOUND);
        }
        return ApiResponse.success(dept);
    }

    @Operation(summary = "更新部门", description = "更新部门信息")
    @PutMapping("/{id}")
    @PreAuthorize("hasRole('ADMIN')")
    public ApiResponse<SysDept> updateDept(@PathVariable String id, @Valid @RequestBody UpdateDeptRequest request) {
        SysDept dept = deptMapper.selectById(id);
        if (dept == null) {
            throw new BusinessException(ErrorCode.DEPT_NOT_FOUND);
        }

        if (StringUtils.hasText(request.getName())) {
            dept.setName(request.getName());
        }
        if (request.getParentId() != null) {
            dept.setParentId(request.getParentId());
        }

        deptMapper.updateById(dept);
        return ApiResponse.success(dept);
    }

    @Operation(summary = "删除部门", description = "删除部门")
    @DeleteMapping("/{id}")
    @PreAuthorize("hasRole('ADMIN')")
    public ApiResponse<Void> deleteDept(@PathVariable String id) {
        SysDept dept = deptMapper.selectById(id);
        if (dept == null) {
            throw new BusinessException(ErrorCode.DEPT_NOT_FOUND);
        }
        deptMapper.deleteById(id);
        return ApiResponse.success();
    }
}
