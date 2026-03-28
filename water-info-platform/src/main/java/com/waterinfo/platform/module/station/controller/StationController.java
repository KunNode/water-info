package com.waterinfo.platform.module.station.controller;

import com.waterinfo.platform.common.api.ApiResponse;
import com.waterinfo.platform.common.api.PageResponse;
import com.waterinfo.platform.module.station.dto.CreateStationRequest;
import com.waterinfo.platform.module.station.dto.StationQueryRequest;
import com.waterinfo.platform.module.station.dto.UpdateStationRequest;
import com.waterinfo.platform.module.station.service.StationService;
import com.waterinfo.platform.module.station.vo.StationVO;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

/**
 * Station management controller
 */
@Tag(name = "站点管理", description = "站点管理相关接口")
@RestController
@RequestMapping("/api/v1/stations")
@RequiredArgsConstructor
public class StationController {

    private final StationService stationService;

    @Operation(summary = "创建站点", description = "创建新的监测站点")
    @PostMapping
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR')")
    public ApiResponse<StationVO> createStation(@Valid @RequestBody CreateStationRequest request) {
        StationVO station = stationService.createStation(request);
        return ApiResponse.success(station);
    }

    @Operation(summary = "根据ID获取站点", description = "根据站点ID获取站点详情")
    @GetMapping("/{id}")
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR', 'VIEWER')")
    public ApiResponse<StationVO> getStationById(@PathVariable String id) {
        StationVO station = stationService.getStationById(id);
        return ApiResponse.success(station);
    }

    @Operation(summary = "查询站点", description = "按分页和筛选条件查询站点")
    @GetMapping
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR', 'VIEWER')")
    public ApiResponse<PageResponse<StationVO>> queryStations(
            @RequestParam(defaultValue = "1") Integer page,
            @RequestParam(defaultValue = "20") Integer size,
            @RequestParam(required = false) String type,
            @RequestParam(required = false) String adminRegion,
            @RequestParam(required = false) String status,
            @RequestParam(required = false) String keyword) {
        
        StationQueryRequest request = new StationQueryRequest();
        request.setPage(page);
        request.setSize(size);
        request.setType(type);
        request.setAdminRegion(adminRegion);
        request.setStatus(status);
        request.setKeyword(keyword);
        
        var result = stationService.queryStations(request);
        return ApiResponse.success(PageResponse.of(result));
    }

    @Operation(summary = "更新站点", description = "更新站点信息")
    @PutMapping("/{id}")
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR')")
    public ApiResponse<StationVO> updateStation(@PathVariable String id, @Valid @RequestBody UpdateStationRequest request) {
        StationVO station = stationService.updateStation(id, request);
        return ApiResponse.success(station);
    }

    @Operation(summary = "删除站点", description = "删除站点")
    @DeleteMapping("/{id}")
    @PreAuthorize("hasRole('ADMIN')")
    public ApiResponse<Void> deleteStation(@PathVariable String id) {
        stationService.deleteStation(id);
        return ApiResponse.success();
    }
}
