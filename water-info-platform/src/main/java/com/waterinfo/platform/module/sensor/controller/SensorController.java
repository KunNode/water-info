package com.waterinfo.platform.module.sensor.controller;

import com.waterinfo.platform.common.api.ApiResponse;
import com.waterinfo.platform.common.api.PageRequest;
import com.waterinfo.platform.common.api.PageResponse;
import com.waterinfo.platform.module.sensor.dto.CreateSensorRequest;
import com.waterinfo.platform.module.sensor.dto.UpdateSensorRequest;
import com.waterinfo.platform.module.sensor.service.SensorService;
import com.waterinfo.platform.module.sensor.vo.SensorVO;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

/**
 * Sensor management controller
 */
@Tag(name = "传感器管理", description = "传感器管理相关接口")
@RestController
@RequestMapping("/api/v1/sensors")
@RequiredArgsConstructor
public class SensorController {

    private final SensorService sensorService;

    @Operation(summary = "创建传感器", description = "创建新传感器")
    @PostMapping
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR')")
    public ApiResponse<SensorVO> createSensor(@Valid @RequestBody CreateSensorRequest request) {
        SensorVO sensor = sensorService.createSensor(request);
        return ApiResponse.success(sensor);
    }

    @Operation(summary = "根据ID获取传感器", description = "根据传感器ID获取传感器详情")
    @GetMapping("/{id}")
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR', 'VIEWER')")
    public ApiResponse<SensorVO> getSensorById(@PathVariable String id) {
        SensorVO sensor = sensorService.getSensorById(id);
        return ApiResponse.success(sensor);
    }

    @Operation(summary = "查询传感器", description = "按分页和筛选条件查询传感器")
    @GetMapping
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR', 'VIEWER')")
    public ApiResponse<PageResponse<SensorVO>> querySensors(
            @RequestParam(defaultValue = "1") Integer page,
            @RequestParam(defaultValue = "20") Integer size,
            @RequestParam(required = false) String stationId,
            @RequestParam(required = false) String type,
            @RequestParam(required = false) String status) {
        
        PageRequest pageRequest = new PageRequest();
        pageRequest.setPage(page);
        pageRequest.setSize(size);
        
        var result = sensorService.querySensors(pageRequest, stationId, type, status);
        return ApiResponse.success(PageResponse.of(result));
    }

    @Operation(summary = "更新传感器", description = "更新传感器信息")
    @PutMapping("/{id}")
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR')")
    public ApiResponse<SensorVO> updateSensor(@PathVariable String id, @Valid @RequestBody UpdateSensorRequest request) {
        SensorVO sensor = sensorService.updateSensor(id, request);
        return ApiResponse.success(sensor);
    }

    @Operation(summary = "更新传感器状态", description = "更新传感器状态")
    @PutMapping("/{id}/status")
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR')")
    public ApiResponse<SensorVO> updateSensorStatus(@PathVariable String id, @RequestParam String status) {
        UpdateSensorRequest request = new UpdateSensorRequest();
        request.setStatus(status);
        SensorVO sensor = sensorService.updateSensor(id, request);
        return ApiResponse.success(sensor);
    }

    @Operation(summary = "更新传感器心跳", description = "更新传感器最近在线时间")
    @PutMapping("/{id}/heartbeat")
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR')")
    public ApiResponse<Void> updateHeartbeat(@PathVariable String id) {
        sensorService.updateHeartbeat(id);
        return ApiResponse.success();
    }

    @Operation(summary = "删除传感器", description = "删除传感器")
    @DeleteMapping("/{id}")
    @PreAuthorize("hasRole('ADMIN')")
    public ApiResponse<Void> deleteSensor(@PathVariable String id) {
        sensorService.deleteSensor(id);
        return ApiResponse.success();
    }
}
