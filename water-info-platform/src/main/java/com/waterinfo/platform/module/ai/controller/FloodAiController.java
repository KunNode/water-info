package com.waterinfo.platform.module.ai.controller;

import com.waterinfo.platform.common.api.ApiResponse;
import com.waterinfo.platform.module.ai.client.AiServiceClient;
import com.waterinfo.platform.module.ai.dto.ConversationDetail;
import com.waterinfo.platform.module.ai.dto.ConversationItem;
import com.waterinfo.platform.module.ai.dto.CreateConversationResponse;
import com.waterinfo.platform.module.ai.dto.FloodPlanPageResponse;
import com.waterinfo.platform.module.ai.dto.FloodPlanResponse;
import com.waterinfo.platform.module.ai.dto.FloodQueryRequest;
import com.waterinfo.platform.module.ai.dto.FloodQueryResponse;
import com.waterinfo.platform.module.ai.dto.PlanExecuteResponse;
import com.waterinfo.platform.module.ai.dto.SessionResponse;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import com.fasterxml.jackson.databind.JsonNode;
import org.springframework.http.MediaType;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.bind.annotation.*;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

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
        // Spring WebFlux automatically prepends "data:" when serialising Flux<String>
        // as text/event-stream — do NOT add the prefix here to avoid doubling it.
        return aiServiceClient.queryFloodStream(request);
    }

    @Operation(summary = "获取应急预案列表", description = "分页获取AI生成的应急预案列表")
    @GetMapping("/plans")
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR', 'VIEWER')")
    public Mono<ApiResponse<FloodPlanPageResponse>> getPlans(
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
    public Mono<ApiResponse<PlanExecuteResponse>> executePlan(@PathVariable String id) {
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

    // ── Conversation (session with memory) ──────────────────────────────────

    @Operation(summary = "会话列表", description = "获取所有会话列表（含最近消息预览）")
    @GetMapping("/conversations")
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR', 'VIEWER')")
    public Mono<ApiResponse<java.util.List<ConversationItem>>> listConversations(
            @RequestParam(defaultValue = "50") int limit,
            @RequestParam(defaultValue = "0") int offset) {
        return aiServiceClient.listConversations(limit, offset)
                .map(ApiResponse::success);
    }

    @Operation(summary = "获取会话详情", description = "获取会话元数据和业务快照（不含消息）")
    @GetMapping("/conversations/{sessionId}")
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR', 'VIEWER')")
    public Mono<ApiResponse<ConversationDetail>> getConversation(@PathVariable String sessionId) {
        return aiServiceClient.getConversation(sessionId)
                .map(ApiResponse::success);
    }

    @Operation(summary = "获取会话消息", description = "根据会话ID获取完整消息历史")
    @GetMapping("/conversations/{sessionId}/messages")
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR', 'VIEWER')")
    public Mono<ApiResponse<ConversationDetail>> getConversationMessages(
            @PathVariable String sessionId,
            @RequestParam(defaultValue = "40") int limit,
            @RequestParam(required = false) Long beforeId) {
        return aiServiceClient.getConversationMessages(sessionId)
                .map(ApiResponse::success);
    }

    @Operation(summary = "新建会话", description = "创建一个新的会话")
    @PostMapping("/conversations")
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR', 'VIEWER')")
    public Mono<ApiResponse<CreateConversationResponse>> createConversation(
            @RequestBody(required = false) java.util.Map<String, String> body) {
        String title = body != null ? body.getOrDefault("title", null) : null;
        return aiServiceClient.createConversation(title)
                .map(ApiResponse::success);
    }

    @Operation(summary = "重命名会话", description = "修改会话标题")
    @PatchMapping("/conversations/{sessionId}")
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR', 'VIEWER')")
    public Mono<ApiResponse<Void>> renameConversation(
            @PathVariable String sessionId,
            @RequestBody java.util.Map<String, String> body) {
        return aiServiceClient.renameConversation(sessionId, body.getOrDefault("title", ""))
                .then(Mono.just(ApiResponse.<Void>success(null)));
    }

    @Operation(summary = "删除会话", description = "删除指定会话及其所有消息")
    @DeleteMapping("/conversations/{sessionId}")
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR', 'VIEWER')")
    public Mono<ApiResponse<Void>> deleteConversation(@PathVariable String sessionId) {
        return aiServiceClient.deleteConversation(sessionId)
                .then(Mono.just(ApiResponse.<Void>success(null)));
    }

    // ── Knowledge base ──────────────────────────────────────────────────────

    @Operation(summary = "上传知识文档", description = "上传文档到 AI 知识库并异步触发切块与索引")
    @PostMapping(value = "/kb/documents", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    @PreAuthorize("hasRole('ADMIN')")
    public Mono<ApiResponse<JsonNode>> uploadKnowledgeDocument(
            @RequestParam("file") MultipartFile file,
            @RequestParam(value = "title", required = false) String title,
            @RequestParam(value = "source_uri", required = false) String sourceUri) {
        return aiServiceClient.uploadKnowledgeDocument(file, title, sourceUri)
                .map(ApiResponse::success);
    }

    @Operation(summary = "知识文档列表", description = "查看知识库中的文档列表")
    @GetMapping("/kb/documents")
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR')")
    public Mono<ApiResponse<JsonNode>> listKnowledgeDocuments(
            @RequestParam(required = false) String status,
            @RequestParam(value = "source_type", required = false) String sourceType,
            @RequestParam(required = false) String q,
            @RequestParam(defaultValue = "50") int limit,
            @RequestParam(defaultValue = "0") int offset) {
        return aiServiceClient.listKnowledgeDocuments(status, sourceType, q, limit, offset)
                .map(ApiResponse::success);
    }

    @Operation(summary = "知识文档详情", description = "查看单个知识文档详情")
    @GetMapping("/kb/documents/{id}")
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR')")
    public Mono<ApiResponse<JsonNode>> getKnowledgeDocument(@PathVariable String id) {
        return aiServiceClient.getKnowledgeDocument(id)
                .map(ApiResponse::success);
    }

    @Operation(summary = "删除知识文档", description = "软删除知识文档并下线其索引")
    @DeleteMapping("/kb/documents/{id}")
    @PreAuthorize("hasRole('ADMIN')")
    public Mono<ApiResponse<JsonNode>> deleteKnowledgeDocument(@PathVariable String id) {
        return aiServiceClient.deleteKnowledgeDocument(id)
                .map(ApiResponse::success);
    }

    @Operation(summary = "重建知识文档索引", description = "重新切块并重建向量索引")
    @PostMapping("/kb/documents/{id}/reindex")
    @PreAuthorize("hasRole('ADMIN')")
    public Mono<ApiResponse<JsonNode>> reindexKnowledgeDocument(@PathVariable String id) {
        return aiServiceClient.reindexKnowledgeDocument(id)
                .map(ApiResponse::success);
    }

    @Operation(summary = "知识库调试检索", description = "在后台调试知识库检索结果")
    @PostMapping("/kb/search")
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR')")
    public Mono<ApiResponse<JsonNode>> searchKnowledge(@RequestBody JsonNode body) {
        return aiServiceClient.searchKnowledge(body)
                .map(ApiResponse::success);
    }

    @Operation(summary = "知识库统计", description = "查看知识库文档、切块和索引统计")
    @GetMapping("/kb/stats")
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR')")
    public Mono<ApiResponse<JsonNode>> getKnowledgeStats() {
        return aiServiceClient.getKnowledgeStats()
                .map(ApiResponse::success);
    }
}
