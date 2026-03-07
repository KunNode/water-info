package com.waterinfo.platform.module.user.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.waterinfo.platform.common.api.ApiResponse;
import com.waterinfo.platform.common.api.PageResponse;
import com.waterinfo.platform.common.exception.BusinessException;
import com.waterinfo.platform.common.exception.ErrorCode;
import com.waterinfo.platform.module.user.entity.SysOrg;
import com.waterinfo.platform.module.user.mapper.SysOrgMapper;
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
 * Organization management controller
 */
@Tag(name = "组织机构", description = "组织机构管理相关接口")
@RestController
@RequestMapping("/api/v1/orgs")
@RequiredArgsConstructor
public class OrgController {

    private final SysOrgMapper orgMapper;

    @Data
    public static class CreateOrgRequest {
        @NotBlank(message = "Name is required")
        private String name;
        @NotBlank(message = "Code is required")
        private String code;
        private String region;
    }

    @Data
    public static class UpdateOrgRequest {
        private String name;
        private String region;
    }

    @Operation(summary = "创建组织", description = "创建新的组织机构")
    @PostMapping
    @PreAuthorize("hasRole('ADMIN')")
    public ApiResponse<SysOrg> createOrg(@Valid @RequestBody CreateOrgRequest request) {
        // Check code uniqueness
        if (orgMapper.selectCount(new LambdaQueryWrapper<SysOrg>().eq(SysOrg::getCode, request.getCode())) > 0) {
            throw new BusinessException(ErrorCode.ORG_CODE_EXISTS);
        }

        SysOrg org = SysOrg.builder()
                .name(request.getName())
                .code(request.getCode())
                .region(request.getRegion())
                .build();
        orgMapper.insert(org);
        return ApiResponse.success(org);
    }

    @Operation(summary = "查询组织列表", description = "分页查询组织机构列表")
    @GetMapping
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR', 'VIEWER')")
    public ApiResponse<PageResponse<SysOrg>> getOrgs(
            @RequestParam(defaultValue = "1") Integer page,
            @RequestParam(defaultValue = "20") Integer size,
            @RequestParam(required = false) String keyword) {
        
        Page<SysOrg> pageObj = new Page<>(page, size);
        LambdaQueryWrapper<SysOrg> wrapper = new LambdaQueryWrapper<>();
        
        if (StringUtils.hasText(keyword)) {
            wrapper.like(SysOrg::getName, keyword).or().like(SysOrg::getCode, keyword);
        }
        wrapper.orderByAsc(SysOrg::getCode);
        
        Page<SysOrg> result = orgMapper.selectPage(pageObj, wrapper);
        return ApiResponse.success(PageResponse.of(result));
    }

    @Operation(summary = "根据ID获取组织", description = "根据组织ID获取组织详情")
    @GetMapping("/{id}")
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR', 'VIEWER')")
    public ApiResponse<SysOrg> getOrgById(@PathVariable String id) {
        SysOrg org = orgMapper.selectById(id);
        if (org == null) {
            throw new BusinessException(ErrorCode.ORG_NOT_FOUND);
        }
        return ApiResponse.success(org);
    }

    @Operation(summary = "更新组织", description = "更新组织机构信息")
    @PutMapping("/{id}")
    @PreAuthorize("hasRole('ADMIN')")
    public ApiResponse<SysOrg> updateOrg(@PathVariable String id, @Valid @RequestBody UpdateOrgRequest request) {
        SysOrg org = orgMapper.selectById(id);
        if (org == null) {
            throw new BusinessException(ErrorCode.ORG_NOT_FOUND);
        }

        if (StringUtils.hasText(request.getName())) {
            org.setName(request.getName());
        }
        if (StringUtils.hasText(request.getRegion())) {
            org.setRegion(request.getRegion());
        }

        orgMapper.updateById(org);
        return ApiResponse.success(org);
    }

    @Operation(summary = "删除组织", description = "删除组织机构")
    @DeleteMapping("/{id}")
    @PreAuthorize("hasRole('ADMIN')")
    public ApiResponse<Void> deleteOrg(@PathVariable String id) {
        SysOrg org = orgMapper.selectById(id);
        if (org == null) {
            throw new BusinessException(ErrorCode.ORG_NOT_FOUND);
        }
        orgMapper.deleteById(id);
        return ApiResponse.success();
    }
}
