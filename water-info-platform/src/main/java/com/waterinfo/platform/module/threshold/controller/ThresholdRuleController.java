package com.waterinfo.platform.module.threshold.controller;

import com.waterinfo.platform.common.api.ApiResponse;
import com.waterinfo.platform.common.api.PageRequest;
import com.waterinfo.platform.common.api.PageResponse;
import com.waterinfo.platform.module.threshold.dto.CreateThresholdRuleRequest;
import com.waterinfo.platform.module.threshold.dto.UpdateThresholdRuleRequest;
import com.waterinfo.platform.module.threshold.service.ThresholdRuleService;
import com.waterinfo.platform.module.threshold.vo.ThresholdRuleVO;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

/**
 * Threshold rule management controller
 */
@Tag(name = "阈值规则", description = "阈值规则管理相关接口")
@RestController
@RequestMapping("/api/v1/threshold-rules")
@RequiredArgsConstructor
public class ThresholdRuleController {

    private final ThresholdRuleService thresholdRuleService;

    @Operation(summary = "创建阈值规则", description = "创建新的阈值规则")
    @PostMapping
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR')")
    public ApiResponse<ThresholdRuleVO> createRule(@Valid @RequestBody CreateThresholdRuleRequest request) {
        ThresholdRuleVO rule = thresholdRuleService.createRule(request);
        return ApiResponse.success(rule);
    }

    @Operation(summary = "根据ID获取阈值规则", description = "根据阈值规则ID获取详情")
    @GetMapping("/{id}")
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR', 'VIEWER')")
    public ApiResponse<ThresholdRuleVO> getRuleById(@PathVariable String id) {
        ThresholdRuleVO rule = thresholdRuleService.getRuleById(id);
        return ApiResponse.success(rule);
    }

    @Operation(summary = "查询阈值规则", description = "按分页和筛选条件查询阈值规则")
    @GetMapping
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR', 'VIEWER')")
    public ApiResponse<PageResponse<ThresholdRuleVO>> queryRules(
            @RequestParam(defaultValue = "1") Integer page,
            @RequestParam(defaultValue = "20") Integer size,
            @RequestParam(required = false) String stationId,
            @RequestParam(required = false) String metricType,
            @RequestParam(required = false) Boolean enabled) {
        
        PageRequest pageRequest = new PageRequest();
        pageRequest.setPage(page);
        pageRequest.setSize(size);
        
        var result = thresholdRuleService.queryRules(pageRequest, stationId, metricType, enabled);
        return ApiResponse.success(PageResponse.of(result));
    }

    @Operation(summary = "更新阈值规则", description = "更新阈值规则信息")
    @PutMapping("/{id}")
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR')")
    public ApiResponse<ThresholdRuleVO> updateRule(@PathVariable String id, @Valid @RequestBody UpdateThresholdRuleRequest request) {
        ThresholdRuleVO rule = thresholdRuleService.updateRule(id, request);
        return ApiResponse.success(rule);
    }

    @Operation(summary = "启用阈值规则", description = "启用指定阈值规则")
    @PutMapping("/{id}/enable")
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR')")
    public ApiResponse<Void> enableRule(@PathVariable String id) {
        thresholdRuleService.enableRule(id);
        return ApiResponse.success();
    }

    @Operation(summary = "停用阈值规则", description = "停用指定阈值规则")
    @PutMapping("/{id}/disable")
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR')")
    public ApiResponse<Void> disableRule(@PathVariable String id) {
        thresholdRuleService.disableRule(id);
        return ApiResponse.success();
    }

    @Operation(summary = "删除阈值规则", description = "删除阈值规则")
    @DeleteMapping("/{id}")
    @PreAuthorize("hasRole('ADMIN')")
    public ApiResponse<Void> deleteRule(@PathVariable String id) {
        thresholdRuleService.deleteRule(id);
        return ApiResponse.success();
    }
}
