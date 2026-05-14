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
import com.waterinfo.platform.module.ai.dto.PlanApproveRequest;
import com.waterinfo.platform.module.ai.dto.PlanApproveResponse;
import com.waterinfo.platform.module.ai.dto.PlanAuditListResponse;
import com.waterinfo.platform.module.ai.dto.PlanEditRequest;
import com.waterinfo.platform.module.ai.dto.PlanExecuteResponse;
import com.waterinfo.platform.module.ai.dto.SessionResponse;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import com.fasterxml.jackson.databind.JsonNode;
import org.springframework.http.CacheControl;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.servlet.mvc.method.annotation.StreamingResponseBody;
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
    public ResponseEntity<StreamingResponseBody> queryFloodStream(@Valid @RequestBody FloodQueryRequest request) {
        log.info("Flood stream query request: {}", request.getQuery());
        return ResponseEntity.ok()
                .contentType(MediaType.TEXT_EVENT_STREAM)
                .cacheControl(CacheControl.noCache())
                .header(HttpHeaders.CONNECTION, "keep-alive")
                .header("X-Accel-Buffering", "no")
                .body(aiServiceClient.streamFloodQuery(request));
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

    @Operation(summary = "编辑应急预案", description = "编辑应急预案内容（摘要、行动、资源、通知）")
    @PatchMapping("/plans/{id}")
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR')")
    public Mono<ApiResponse<FloodPlanResponse>> updatePlan(
            @PathVariable String id,
            @Valid @RequestBody PlanEditRequest request) {
        log.info("Update plan request: {}", id);
        return aiServiceClient.updatePlan(id, request)
                .map(ApiResponse::success);
    }

    @Operation(summary = "批准应急预案", description = "批准草案预案（draft → approved）")
    @PostMapping("/plans/{id}/approve")
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR')")
    public Mono<ApiResponse<PlanApproveResponse>> approvePlan(
            @PathVariable String id,
            @Valid @RequestBody PlanApproveRequest request) {
        log.info("Approve plan request: {}", id);
        return aiServiceClient.approvePlan(id, request)
                .map(ApiResponse::success);
    }

    @Operation(summary = "获取预案审计记录", description = "按时间倒序返回预案的审计记录列表")
    @GetMapping("/plans/{id}/audits")
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR', 'VIEWER')")
    public Mono<ApiResponse<PlanAuditListResponse>> listPlanAudits(@PathVariable String id) {
        log.debug("List plan audits request: {}", id);
        return aiServiceClient.listPlanAudits(id)
                .map(ApiResponse::success);
    }

    @Operation(summary = "获取预案执行进度", description = "获取预案执行的实时进度（行动项状态）")
    @GetMapping("/plans/{id}/progress")
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR', 'VIEWER')")
    public Mono<ApiResponse<JsonNode>> getPlanProgress(@PathVariable String id) {
        log.debug("Get plan progress request: {}", id);
        return aiServiceClient.getPlanProgress(id)
                .map(ApiResponse::success);
    }

    @Operation(summary = "更新行动项状态", description = "执行中手动更新某个行动项的状态")
    @PatchMapping("/plans/{planId}/actions/{actionId}")
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR')")
    public Mono<ApiResponse<JsonNode>> updateActionStatus(
            @PathVariable String planId,
            @PathVariable String actionId,
            @RequestBody java.util.Map<String, String> body) {
        log.info("Update action status: {}/{} -> {}", planId, actionId, body.get("status"));
        return aiServiceClient.updateActionStatus(planId, actionId, body.getOrDefault("status", ""))
                .map(ApiResponse::success);
    }

    @Operation(summary = "取消预案执行", description = "取消正在执行的预案")
    @PostMapping("/plans/{id}/cancel")
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR')")
    public Mono<ApiResponse<JsonNode>> cancelPlan(@PathVariable String id) {
        log.info("Cancel plan request: {}", id);
        return aiServiceClient.cancelPlan(id)
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
    public ApiResponse<java.util.List<ConversationItem>> listConversations(
            @RequestParam(defaultValue = "50") int limit,
            @RequestParam(defaultValue = "0") int offset) {
        java.util.List<ConversationItem> conversations = aiServiceClient.listConversations(limit, offset).block();
        return ApiResponse.success(conversations == null ? java.util.List.of() : conversations);
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
        return aiServiceClient.getConversationMessages(sessionId, limit, beforeId)
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

    @Operation(summary = "记忆列表", description = "获取当前用户或会话可见的 AI 长期记忆")
    @GetMapping("/memory")
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR', 'VIEWER')")
    public Mono<ApiResponse<JsonNode>> listMemory(
            @RequestParam(value = "session_id", required = false) String sessionId,
            @RequestParam(defaultValue = "50") int limit,
            @RequestParam(defaultValue = "0") int offset) {
        return aiServiceClient.listMemory(sessionId, limit, offset)
                .map(ApiResponse::success);
    }

    @Operation(summary = "用户记忆列表", description = "获取当前用户命名空间下的 AI 长期记忆")
    @GetMapping("/memory/user")
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR', 'VIEWER')")
    public Mono<ApiResponse<JsonNode>> listUserMemory(
            @RequestParam(defaultValue = "50") int limit,
            @RequestParam(defaultValue = "0") int offset) {
        return aiServiceClient.listUserMemory(limit, offset)
                .map(ApiResponse::success);
    }

    @Operation(summary = "更新记忆", description = "更新或禁用一条 AI 长期记忆")
    @PatchMapping("/memory/{memoryId}")
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR')")
    public Mono<ApiResponse<JsonNode>> updateMemory(
            @PathVariable long memoryId,
            @RequestParam(value = "session_id", required = false) String sessionId,
            @RequestBody java.util.Map<String, Object> body) {
        return aiServiceClient.updateMemory(memoryId, body, sessionId)
                .map(ApiResponse::success);
    }

    @Operation(summary = "删除记忆", description = "软删除一条 AI 长期记忆")
    @DeleteMapping("/memory/{memoryId}")
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR')")
    public Mono<ApiResponse<Void>> deleteMemory(
            @PathVariable long memoryId,
            @RequestParam(value = "session_id", required = false) String sessionId) {
        return aiServiceClient.deleteMemory(memoryId, sessionId)
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
