package com.waterinfo.platform.module.alarm.controller;

import com.waterinfo.platform.common.api.ApiResponse;
import com.waterinfo.platform.common.api.PageResponse;
import com.waterinfo.platform.module.alarm.dto.AlarmQueryRequest;
import com.waterinfo.platform.module.alarm.service.AlarmService;
import com.waterinfo.platform.module.alarm.vo.AlarmVO;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;

/**
 * Alarm management controller
 */
@Tag(name = "告警管理", description = "告警管理相关接口")
@RestController
@RequestMapping("/api/v1/alarms")
@RequiredArgsConstructor
public class AlarmController {

    private final AlarmService alarmService;

    @Operation(summary = "查询告警", description = "按分页和筛选条件查询告警")
    @GetMapping
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR', 'VIEWER')")
    public ApiResponse<PageResponse<AlarmVO>> queryAlarms(
            @RequestParam(defaultValue = "1") Integer page,
            @RequestParam(defaultValue = "20") Integer size,
            @RequestParam(required = false) String stationId,
            @RequestParam(required = false) String metricType,
            @RequestParam(required = false) String level,
            @RequestParam(required = false) String status,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) LocalDateTime start,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) LocalDateTime end) {
        
        AlarmQueryRequest request = new AlarmQueryRequest();
        request.setPage(page);
        request.setSize(size);
        request.setStationId(stationId);
        request.setMetricType(metricType);
        request.setLevel(level);
        request.setStatus(status);
        request.setStart(start);
        request.setEnd(end);
        
        var result = alarmService.queryAlarms(request);
        return ApiResponse.success(PageResponse.of(result));
    }

    @Operation(summary = "根据ID获取告警", description = "根据告警ID获取告警详情")
    @GetMapping("/{id}")
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR', 'VIEWER')")
    public ApiResponse<AlarmVO> getAlarmById(@PathVariable String id) {
        AlarmVO alarm = alarmService.getAlarmById(id);
        return ApiResponse.success(alarm);
    }

    @Operation(summary = "确认告警", description = "确认 OPEN 状态告警（状态流转为 ACK）")
    @PostMapping("/{id}/ack")
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR')")
    public ApiResponse<AlarmVO> acknowledgeAlarm(@PathVariable String id) {
        AlarmVO alarm = alarmService.acknowledgeAlarm(id);
        return ApiResponse.success(alarm);
    }

    @Operation(summary = "关闭告警", description = "关闭告警（从 OPEN 或 ACK 流转为 CLOSED）")
    @PostMapping("/{id}/close")
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR')")
    public ApiResponse<AlarmVO> closeAlarm(@PathVariable String id) {
        AlarmVO alarm = alarmService.closeAlarm(id);
        return ApiResponse.success(alarm);
    }
}
