package com.waterinfo.platform.module.ai.controller;

import com.waterinfo.platform.common.api.ApiResponse;
import com.waterinfo.platform.module.ai.client.AiServiceClient;
import com.waterinfo.platform.module.ai.dto.FloodPlanResponse;
import com.waterinfo.platform.module.ai.dto.FloodQueryRequest;
import com.waterinfo.platform.module.ai.dto.FloodQueryResponse;
import com.waterinfo.platform.module.ai.dto.SessionResponse;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

import java.util.Map;

/**
 * Flood AI emergency response controller
 * Proxies requests to the Python AI service
 */
@Slf4j
@Tag(name = "洪水应急AI", description = "洪水应急AI智能指挥相关接口")
@RestController
@RequestMapping("/api/v1")
@RequiredArgsConstructor
public class FloodAiController {

    private final AiServiceClient aiServiceClient;

    @Operation(summary = "洪水应急查询", description = "向AI发送洪水应急相关查询，获取非流式响应")
    @PostMapping("/flood/query")
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR', 'VIEWER')")
    public Mono<ApiResponse<FloodQueryResponse>> queryFlood(@Valid @RequestBody FloodQueryRequest request) {
        log.info("Flood query request: {}", request.getQuery());
        return aiServiceClient.queryFlood(request)
                .map(ApiResponse::success);
    }

    @Operation(summary = "洪水应急查询(流式)", description = "向AI发送洪水应急相关查询，获取SSE流式响应")
    @PostMapping(value = "/flood/query/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR', 'VIEWER')")
    public Flux<String> queryFloodStream(@Valid @RequestBody FloodQueryRequest request) {
        log.info("Flood stream query request: {}", request.getQuery());
        return aiServiceClient.queryFloodStream(request)
                .map(data -> {
                    // Ensure proper SSE format
                    if (data.startsWith("data: ")) {
                        return data;
                    }
                    return "data: " + data;
                });
    }

    @Operation(summary = "获取应急预案列表", description = "分页获取AI生成的应急预案列表")
    @GetMapping("/plans")
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR', 'VIEWER')")
    public Mono<ApiResponse<Map<String, Object>>> getPlans(
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int size) {
        log.debug("Get plans request, page: {}, size: {}", page, size);
        return aiServiceClient.getPlans(page, size)
                .map(ApiResponse::success);
    }

    @Operation(summary = "获取应急预案详情", description = "根据ID获取应急预案详情")
    @GetMapping("/plans/{id}")
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR', 'VIEWER')")
    public Mono<ApiResponse<FloodPlanResponse>> getPlan(@PathVariable String id) {
        log.debug("Get plan request: {}", id);
        return aiServiceClient.getPlan(id)
                .map(ApiResponse::success);
    }

    @Operation(summary = "执行应急预案", description = "执行指定的应急预案")
    @PostMapping("/plans/{id}/execute")
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR')")
    public Mono<ApiResponse<FloodPlanResponse>> executePlan(@PathVariable String id) {
        log.info("Execute plan request: {}", id);
        return aiServiceClient.executePlan(id)
                .map(ApiResponse::success);
    }

    @Operation(summary = "获取会话历史", description = "根据会话ID获取历史消息记录")
    @GetMapping("/sessions/{id}")
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR', 'VIEWER')")
    public Mono<ApiResponse<SessionResponse>> getSession(@PathVariable String id) {
        log.debug("Get session request: {}", id);
        return aiServiceClient.getSession(id)
                .map(ApiResponse::success);
    }
}
