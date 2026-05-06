package com.waterinfo.platform.module.resource.controller;

import com.waterinfo.platform.common.api.ApiResponse;
import com.waterinfo.platform.common.api.PageResponse;
import com.waterinfo.platform.module.resource.dto.CreateDispatchRequest;
import com.waterinfo.platform.module.resource.dto.DispatchQueryRequest;
import com.waterinfo.platform.module.resource.dto.UpdateDispatchStatusRequest;
import com.waterinfo.platform.module.resource.service.ResourceDispatchService;
import com.waterinfo.platform.module.resource.vo.ResourceDispatchVO;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@Tag(name = "资源调度", description = "资源调度记录接口")
@RestController
@RequestMapping("/api/v1/resource-dispatches")
@RequiredArgsConstructor
public class ResourceDispatchController {

    private final ResourceDispatchService dispatchService;

    @Operation(summary = "创建调度单")
    @PostMapping
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR')")
    public ApiResponse<ResourceDispatchVO> createDispatch(@Valid @RequestBody CreateDispatchRequest request) {
        return ApiResponse.success(dispatchService.createDispatch(request, request.getSource()));
    }

    @Operation(summary = "调度详情")
    @GetMapping("/{id}")
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR', 'VIEWER')")
    public ApiResponse<ResourceDispatchVO> getDispatch(@PathVariable String id) {
        return ApiResponse.success(dispatchService.getDispatchById(id));
    }

    @Operation(summary = "查询调度记录")
    @GetMapping
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR', 'VIEWER')")
    public ApiResponse<PageResponse<ResourceDispatchVO>> queryDispatches(
            @RequestParam(defaultValue = "1") Integer page,
            @RequestParam(defaultValue = "20") Integer size,
            @RequestParam(required = false) String resourceId,
            @RequestParam(required = false) String planId,
            @RequestParam(required = false) String status,
            @RequestParam(required = false) String source) {
        DispatchQueryRequest request = new DispatchQueryRequest();
        request.setPage(page);
        request.setSize(size);
        request.setResourceId(resourceId);
        request.setPlanId(planId);
        request.setStatus(status);
        request.setSource(source);

        return ApiResponse.success(PageResponse.of(dispatchService.queryDispatches(request)));
    }

    @Operation(summary = "更新调度状态")
    @PatchMapping("/{id}/status")
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR')")
    public ApiResponse<ResourceDispatchVO> updateDispatchStatus(
            @PathVariable String id,
            @Valid @RequestBody UpdateDispatchStatusRequest request) {
        return ApiResponse.success(dispatchService.updateStatus(id, request));
    }
}
