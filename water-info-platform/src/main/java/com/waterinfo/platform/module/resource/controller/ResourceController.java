package com.waterinfo.platform.module.resource.controller;

import com.waterinfo.platform.common.api.ApiResponse;
import com.waterinfo.platform.common.api.PageResponse;
import com.waterinfo.platform.module.resource.dto.CreateResourceRequest;
import com.waterinfo.platform.module.resource.dto.ResourceQueryRequest;
import com.waterinfo.platform.module.resource.dto.UpdateResourceRequest;
import com.waterinfo.platform.module.resource.service.ResourceService;
import com.waterinfo.platform.module.resource.vo.ResourceStatsVO;
import com.waterinfo.platform.module.resource.vo.ResourceVO;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@Tag(name = "资源管理", description = "应急资源管理接口")
@RestController
@RequestMapping("/api/v1/resources")
@RequiredArgsConstructor
public class ResourceController {

    private final ResourceService resourceService;

    @Operation(summary = "创建资源")
    @PostMapping
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR')")
    public ApiResponse<ResourceVO> createResource(@Valid @RequestBody CreateResourceRequest request) {
        return ApiResponse.success(resourceService.createResource(request));
    }

    @Operation(summary = "资源详情")
    @GetMapping("/{id}")
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR', 'VIEWER')")
    public ApiResponse<ResourceVO> getResource(@PathVariable String id) {
        return ApiResponse.success(resourceService.getResourceById(id));
    }

    @Operation(summary = "查询资源列表")
    @GetMapping
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR', 'VIEWER')")
    public ApiResponse<PageResponse<ResourceVO>> queryResources(
            @RequestParam(defaultValue = "1") Integer page,
            @RequestParam(defaultValue = "20") Integer size,
            @RequestParam(required = false) String type,
            @RequestParam(required = false) String status,
            @RequestParam(required = false) String keyword) {
        ResourceQueryRequest request = new ResourceQueryRequest();
        request.setPage(page);
        request.setSize(size);
        request.setType(type);
        request.setStatus(status);
        request.setKeyword(keyword);

        return ApiResponse.success(PageResponse.of(resourceService.queryResources(request)));
    }

    @Operation(summary = "更新资源")
    @PutMapping("/{id}")
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR')")
    public ApiResponse<ResourceVO> updateResource(@PathVariable String id, @Valid @RequestBody UpdateResourceRequest request) {
        return ApiResponse.success(resourceService.updateResource(id, request));
    }

    @Operation(summary = "删除资源")
    @DeleteMapping("/{id}")
    @PreAuthorize("hasRole('ADMIN')")
    public ApiResponse<Void> deleteResource(@PathVariable String id) {
        resourceService.deleteResource(id);
        return ApiResponse.success();
    }

    @Operation(summary = "资源统计")
    @GetMapping("/stats")
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR', 'VIEWER')")
    public ApiResponse<List<ResourceStatsVO>> getStats() {
        return ApiResponse.success(resourceService.getStats());
    }

    @Operation(summary = "可用资源查询")
    @GetMapping("/available")
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR', 'VIEWER')")
    public ApiResponse<List<ResourceVO>> getAvailableResources(
            @RequestParam(required = false) String type,
            @RequestParam(required = false) String location) {
        return ApiResponse.success(resourceService.getAvailableResources(type, location));
    }
}
