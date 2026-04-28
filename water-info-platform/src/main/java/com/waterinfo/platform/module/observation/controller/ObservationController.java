package com.waterinfo.platform.module.observation.controller;

import com.waterinfo.platform.common.api.ApiResponse;
import com.waterinfo.platform.common.api.PageResponse;
import com.waterinfo.platform.module.observation.dto.BatchObservationRequest;
import com.waterinfo.platform.module.observation.dto.BatchObservationResponse;
import com.waterinfo.platform.module.observation.dto.LatestObservationBatchRequest;
import com.waterinfo.platform.module.observation.dto.ObservationQueryRequest;
import com.waterinfo.platform.module.observation.service.ObservationService;
import com.waterinfo.platform.module.observation.vo.ObservationVO;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.ExampleObject;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.util.List;

/**
 * Observation data controller
 */
@Tag(name = "观测数据", description = "观测数据相关接口（时序）")
@RestController
@RequestMapping("/api/v1/observations")
@RequiredArgsConstructor
public class ObservationController {

    private final ObservationService observationService;

    @Operation(
            summary = "批量上报观测数据",
            description = "批量上传观测数据（1-5000 条），并自动触发阈值评估。",
            requestBody = @io.swagger.v3.oas.annotations.parameters.RequestBody(
                    content = @Content(
                            schema = @Schema(implementation = BatchObservationRequest.class),
                            examples = @ExampleObject(
                                    name = "批量上报示例",
                                    value = """
                                            {
                                              "requestId": "batch-2024-001",
                                              "observations": [
                                                {
                                                  "stationId": "station-uuid-1",
                                                  "metricType": "WATER_LEVEL",
                                                  "value": 12.5,
                                                  "unit": "m",
                                                  "observedAt": "2024-01-15T10:30:00",
                                                  "qualityFlag": "GOOD",
                                                  "source": "sensor-001"
                                                },
                                                {
                                                  "stationId": "station-uuid-1",
                                                  "metricType": "RAINFALL",
                                                  "value": 5.2,
                                                  "unit": "mm",
                                                  "observedAt": "2024-01-15T10:30:00",
                                                  "qualityFlag": "GOOD",
                                                  "source": "sensor-002"
                                                }
                                              ]
                                            }
                                            """
                            )
                    )
            )
    )
    @PostMapping("/batch")
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR')")
    public ApiResponse<BatchObservationResponse> batchUpload(@Valid @RequestBody BatchObservationRequest request) {
        BatchObservationResponse response = observationService.batchUpload(request);
        return ApiResponse.success(response);
    }

    @Operation(summary = "查询观测数据", description = "按分页和筛选条件查询观测数据")
    @GetMapping
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR', 'VIEWER')")
    public ApiResponse<PageResponse<ObservationVO>> queryObservations(
            @RequestParam(defaultValue = "1") Integer page,
            @RequestParam(defaultValue = "20") Integer size,
            @RequestParam(required = false) String stationId,
            @RequestParam(required = false) String metricType,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) LocalDateTime start,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) LocalDateTime end) {
        
        ObservationQueryRequest request = new ObservationQueryRequest();
        request.setPage(page);
        request.setSize(size);
        request.setStationId(stationId);
        request.setMetricType(metricType);
        request.setStart(start);
        request.setEnd(end);
        
        var result = observationService.queryObservations(request);
        return ApiResponse.success(PageResponse.of(result));
    }

    @Operation(summary = "获取最新观测数据", description = "获取指定站点和指标类型的最新观测数据")
    @GetMapping("/latest")
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR', 'VIEWER')")
    public ApiResponse<ObservationVO> getLatestObservation(
            @RequestParam String stationId,
            @RequestParam(required = false) String metricType) {
        ObservationVO observation = observationService.getLatestObservation(stationId, metricType);
        return ApiResponse.success(observation);
    }

    @Operation(summary = "批量获取最新观测数据", description = "按站点和指标类型批量获取最新观测数据")
    @PostMapping("/latest/batch")
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR', 'VIEWER')")
    public ApiResponse<List<ObservationVO>> getLatestObservations(
            @Valid @RequestBody LatestObservationBatchRequest request) {
        List<ObservationVO> observations = observationService.getLatestObservations(request.getItems());
        return ApiResponse.success(observations);
    }
}
