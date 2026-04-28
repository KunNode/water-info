package com.waterinfo.platform.module.ai.client;

import com.fasterxml.jackson.databind.JsonNode;
import com.waterinfo.platform.module.ai.config.AiServiceProperties;
import com.waterinfo.platform.module.ai.context.AiUserContext;
import com.waterinfo.platform.module.ai.context.AiUserContext.UserInfo;
import com.waterinfo.platform.module.ai.dto.ConversationDetail;
import com.waterinfo.platform.module.ai.dto.ConversationItem;
import com.waterinfo.platform.module.ai.dto.CreateConversationResponse;
import com.waterinfo.platform.module.ai.dto.FloodPlanPageResponse;
import com.waterinfo.platform.module.ai.dto.FloodPlanResponse;
import com.waterinfo.platform.module.ai.dto.FloodQueryRequest;
import com.waterinfo.platform.module.ai.dto.FloodQueryResponse;
import com.waterinfo.platform.module.ai.dto.PlanExecuteResponse;
import com.waterinfo.platform.module.ai.dto.SessionResponse;
import jakarta.annotation.PostConstruct;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.core.io.buffer.DataBuffer;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.client.MultipartBodyBuilder;
import org.springframework.stereotype.Component;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.reactive.function.BodyInserters;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

import java.time.Duration;
import java.util.ArrayList;
import java.util.List;

/**
 * AI service client for communicating with the Python AI service.
 * Automatically forwards user identity via X-User-Id and X-Username headers.
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class AiServiceClient {

    private final AiServiceProperties properties;
    private final AiUserContext userContext;
    private WebClient webClient;

    @PostConstruct
    public void init() {
        this.webClient = WebClient.builder()
                .baseUrl(properties.getUrl())
                .defaultHeader(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
                .build();
    }

    /**
     * Execute flood emergency query (non-streaming)
     */
    public Mono<FloodQueryResponse> queryFlood(FloodQueryRequest request) {
        log.debug("Sending flood query to AI service: {}", request.getQuery());

        return userContext.getCurrentUser()
                .flatMap(user -> webClient.post()
                        .uri("/api/v1/flood/query")
                        .headers(headers -> addUserHeaders(headers, user))
                        .bodyValue(request)
                        .retrieve()
                        .bodyToMono(FloodQueryResponse.class)
                        .timeout(Duration.ofSeconds(properties.getTimeoutSeconds()))
                        .doOnError(error -> log.error("Error calling AI service query: {}", error.getMessage())));
    }

    /**
     * Execute flood emergency query with streaming (SSE)
     */
    public Flux<String> queryFloodStream(FloodQueryRequest request) {
        log.debug("Sending flood stream query to AI service: {}", request.getQuery());

        return userContext.getCurrentUser()
                .flatMapMany(user -> webClient.post()
                        .uri("/api/v1/flood/query/stream")
                        .header(HttpHeaders.ACCEPT, MediaType.TEXT_EVENT_STREAM_VALUE)
                        .headers(headers -> addUserHeaders(headers, user))
                        .bodyValue(request)
                        .retrieve()
                        .bodyToFlux(String.class)
                        .doOnError(error -> log.error("Error calling AI service stream: {}", error.getMessage())));
    }

    /**
     * Get list of emergency plans
     */
    public Mono<FloodPlanPageResponse> getPlans(int page, int size) {
        log.debug("Fetching plans from AI service, page: {}, size: {}", page, size);

        int safePage = Math.max(page, 1);
        int safeSize = Math.max(size, 1);
        int offset = (safePage - 1) * safeSize;

        Mono<List<FloodPlanResponse>> recordsMono = webClient.get()
                .uri(uriBuilder -> uriBuilder
                        .path("/api/v1/plans")
                        .queryParam("limit", safeSize)
                        .queryParam("offset", offset)
                        .build())
                .retrieve()
                .bodyToMono(JsonNode.class)
                .map(this::mapPlanList)
                .timeout(Duration.ofSeconds(properties.getTimeoutSeconds()));

        Mono<Long> totalMono = webClient.get()
                .uri("/api/v1/plans/count")
                .retrieve()
                .bodyToMono(JsonNode.class)
                .map(node -> node.path("count").asLong(0))
                .timeout(Duration.ofSeconds(properties.getTimeoutSeconds()));

        return Mono.zip(recordsMono, totalMono)
                .map(tuple -> {
                    FloodPlanPageResponse response = new FloodPlanPageResponse();
                    long total = tuple.getT2();
                    response.setRecords(tuple.getT1());
                    response.setTotal(total);
                    response.setPage(safePage);
                    response.setSize(safeSize);
                    response.setPages((long) Math.ceil(total / (double) safeSize));
                    return response;
                })
                .doOnError(error -> log.error("Error fetching plans: {}", error.getMessage()));
    }

    /**
     * Get plan by ID
     */
    public Mono<FloodPlanResponse> getPlan(String id) {
        log.debug("Fetching plan from AI service: {}", id);

        return webClient.get()
                .uri("/api/v1/plans/{id}", id)
                .retrieve()
                .bodyToMono(JsonNode.class)
                .map(this::mapPlanDetail)
                .timeout(Duration.ofSeconds(properties.getTimeoutSeconds()))
                .doOnError(error -> log.error("Error fetching plan {}: {}", id, error.getMessage()));
    }

    /**
     * Execute a plan
     */
    public Mono<PlanExecuteResponse> executePlan(String id) {
        log.debug("Executing plan on AI service: {}", id);

        return webClient.post()
                .uri("/api/v1/plans/{id}/execute", id)
                .retrieve()
                .bodyToMono(JsonNode.class)
                .map(this::mapPlanExecuteResponse)
                .timeout(Duration.ofSeconds(properties.getTimeoutSeconds()))
                .doOnError(error -> log.error("Error executing plan {}: {}", id, error.getMessage()));
    }

    /**
     * Get session history
     */
    public Mono<SessionResponse> getSession(String id) {
        log.debug("Fetching session from AI service: {}", id);

        return userContext.getCurrentUser()
                .flatMap(user -> webClient.get()
                        .uri("/api/v1/sessions/{id}", id)
                        .headers(headers -> addUserHeaders(headers, user))
                        .retrieve()
                        .bodyToMono(JsonNode.class)
                        .map(this::mapSessionResponse)
                        .timeout(Duration.ofSeconds(properties.getTimeoutSeconds()))
                        .doOnError(error -> log.error("Error fetching session {}: {}", id, error.getMessage())));
    }

    // ── Conversation (session with memory) ──────────────────────────────────

    /**
     * List all conversation sessions for the current user.
     */
    public Mono<List<ConversationItem>> listConversations(int limit, int offset) {
        return userContext.getCurrentUser()
                .flatMap(user -> webClient.get()
                        .uri(u -> u.path("/api/v1/conversations")
                                .queryParam("limit", limit)
                                .queryParam("offset", offset)
                                .build())
                        .headers(headers -> addUserHeaders(headers, user))
                        .retrieve()
                        .bodyToMono(JsonNode.class)
                        .map(this::mapConversationList)
                        .timeout(Duration.ofSeconds(properties.getTimeoutSeconds()))
                        .doOnError(e -> log.error("Error listing conversations: {}", e.getMessage())));
    }

    /**
     * Get messages for a conversation session.
     */
    public Mono<ConversationDetail> getConversationMessages(String sessionId) {
        return userContext.getCurrentUser()
                .flatMap(user -> webClient.get()
                        .uri("/api/v1/conversations/{sessionId}/messages", sessionId)
                        .headers(headers -> addUserHeaders(headers, user))
                        .retrieve()
                        .bodyToMono(JsonNode.class)
                        .map(this::mapConversationDetail)
                        .timeout(Duration.ofSeconds(properties.getTimeoutSeconds()))
                        .doOnError(e -> log.error("Error fetching conversation {}: {}", sessionId, e.getMessage())));
    }

    /**
     * Get full conversation details including session and snapshot.
     */
    public Mono<ConversationDetail> getConversation(String sessionId) {
        return userContext.getCurrentUser()
                .flatMap(user -> webClient.get()
                        .uri("/api/v1/conversations/{sessionId}", sessionId)
                        .headers(headers -> addUserHeaders(headers, user))
                        .retrieve()
                        .bodyToMono(JsonNode.class)
                        .map(this::mapConversationFull)
                        .timeout(Duration.ofSeconds(properties.getTimeoutSeconds()))
                        .doOnError(e -> log.error("Error fetching conversation {}: {}", sessionId, e.getMessage())));
    }

    /**
     * Create a new conversation session.
     */
    public Mono<CreateConversationResponse> createConversation(String title) {
        java.util.Map<String, Object> body = new java.util.HashMap<>();
        if (title != null && !title.isBlank()) body.put("title", title);
        return userContext.getCurrentUser()
                .flatMap(user -> webClient.post()
                        .uri("/api/v1/conversations")
                        .headers(headers -> addUserHeaders(headers, user))
                        .bodyValue(body)
                        .retrieve()
                        .bodyToMono(JsonNode.class)
                        .map(this::mapCreateConversationResponse)
                        .timeout(Duration.ofSeconds(properties.getTimeoutSeconds()))
                        .doOnError(e -> log.error("Error creating conversation: {}", e.getMessage())));
    }

    /**
     * Rename a conversation session.
     */
    public Mono<Void> renameConversation(String sessionId, String title) {
        return userContext.getCurrentUser()
                .flatMap(user -> webClient.patch()
                        .uri("/api/v1/conversations/{sessionId}", sessionId)
                        .headers(headers -> addUserHeaders(headers, user))
                        .bodyValue(java.util.Map.of("title", title))
                        .retrieve()
                        .bodyToMono(Void.class)
                        .timeout(Duration.ofSeconds(properties.getTimeoutSeconds()))
                        .doOnError(e -> log.error("Error renaming conversation {}: {}", sessionId, e.getMessage())));
    }

    /**
     * Delete a conversation session.
     */
    public Mono<Void> deleteConversation(String sessionId) {
        return userContext.getCurrentUser()
                .flatMap(user -> webClient.delete()
                        .uri("/api/v1/conversations/{sessionId}", sessionId)
                        .headers(headers -> addUserHeaders(headers, user))
                        .retrieve()
                        .bodyToMono(Void.class)
                        .timeout(Duration.ofSeconds(properties.getTimeoutSeconds()))
                        .doOnError(e -> log.error("Error deleting conversation {}: {}", sessionId, e.getMessage())));
    }

    // ── Knowledge base ──────────────────────────────────────────────────────

    public Mono<JsonNode> uploadKnowledgeDocument(MultipartFile file, String title, String sourceUri) {
        return userContext.getCurrentUser()
                .flatMap(user -> {
                    MultipartBodyBuilder builder = new MultipartBodyBuilder();
                    var filePart = builder.part("file", file.getResource())
                            .filename(file.getOriginalFilename());
                    if (file.getContentType() != null && !file.getContentType().isBlank()) {
                        filePart.header(HttpHeaders.CONTENT_TYPE, file.getContentType());
                    }
                    if (title != null && !title.isBlank()) {
                        builder.part("title", title);
                    }
                    if (sourceUri != null && !sourceUri.isBlank()) {
                        builder.part("source_uri", sourceUri);
                    }

                    return webClient.post()
                            .uri("/api/v1/kb/documents")
                            .contentType(MediaType.MULTIPART_FORM_DATA)
                            .headers(headers -> {
                                headers.remove(HttpHeaders.CONTENT_TYPE);
                                addUserHeaders(headers, user);
                            })
                            .body(BodyInserters.fromMultipartData(builder.build()))
                            .retrieve()
                            .bodyToMono(JsonNode.class)
                            .timeout(Duration.ofSeconds(properties.getTimeoutSeconds()))
                            .doOnError(e -> log.error("Error uploading knowledge document {}: {}", file.getOriginalFilename(), e.getMessage()));
                });
    }

    public Mono<JsonNode> listKnowledgeDocuments(
            String status,
            String sourceType,
            String q,
            int limit,
            int offset
    ) {
        return webClient.get()
                .uri(uriBuilder -> uriBuilder
                        .path("/api/v1/kb/documents")
                        .queryParamIfPresent("status", java.util.Optional.ofNullable(status))
                        .queryParamIfPresent("source_type", java.util.Optional.ofNullable(sourceType))
                        .queryParamIfPresent("q", java.util.Optional.ofNullable(q))
                        .queryParam("limit", limit)
                        .queryParam("offset", offset)
                        .build())
                .retrieve()
                .bodyToMono(JsonNode.class)
                .timeout(Duration.ofSeconds(properties.getTimeoutSeconds()))
                .doOnError(e -> log.error("Error listing knowledge documents: {}", e.getMessage()));
    }

    public Mono<JsonNode> getKnowledgeDocument(String documentId) {
        return webClient.get()
                .uri("/api/v1/kb/documents/{id}", documentId)
                .retrieve()
                .bodyToMono(JsonNode.class)
                .timeout(Duration.ofSeconds(properties.getTimeoutSeconds()))
                .doOnError(e -> log.error("Error getting knowledge document {}: {}", documentId, e.getMessage()));
    }

    public Mono<JsonNode> deleteKnowledgeDocument(String documentId) {
        return userContext.getCurrentUser()
                .flatMap(user -> webClient.delete()
                        .uri("/api/v1/kb/documents/{id}", documentId)
                        .headers(headers -> addUserHeaders(headers, user))
                        .retrieve()
                        .bodyToMono(JsonNode.class)
                        .timeout(Duration.ofSeconds(properties.getTimeoutSeconds()))
                        .doOnError(e -> log.error("Error deleting knowledge document {}: {}", documentId, e.getMessage())));
    }

    public Mono<JsonNode> reindexKnowledgeDocument(String documentId) {
        return userContext.getCurrentUser()
                .flatMap(user -> webClient.post()
                        .uri("/api/v1/kb/documents/{id}/reindex", documentId)
                        .headers(headers -> addUserHeaders(headers, user))
                        .retrieve()
                        .bodyToMono(JsonNode.class)
                        .timeout(Duration.ofSeconds(properties.getTimeoutSeconds()))
                        .doOnError(e -> log.error("Error reindexing knowledge document {}: {}", documentId, e.getMessage())));
    }

    public Mono<JsonNode> searchKnowledge(JsonNode body) {
        return webClient.post()
                .uri("/api/v1/kb/search")
                .bodyValue(body)
                .retrieve()
                .bodyToMono(JsonNode.class)
                .timeout(Duration.ofSeconds(properties.getTimeoutSeconds()))
                .doOnError(e -> log.error("Error searching knowledge base: {}", e.getMessage()));
    }

    public Mono<JsonNode> getKnowledgeStats() {
        return webClient.get()
                .uri("/api/v1/kb/stats")
                .retrieve()
                .bodyToMono(JsonNode.class)
                .timeout(Duration.ofSeconds(properties.getTimeoutSeconds()))
                .doOnError(e -> log.error("Error getting knowledge stats: {}", e.getMessage()));
    }

    /**
     * Add user identity headers to a request.
     */
    private void addUserHeaders(HttpHeaders headers, UserInfo user) {
        if (user != null && user.isAuthenticated()) {
            headers.set(AiUserContext.HEADER_USER_ID, user.userId());
            headers.set(AiUserContext.HEADER_USERNAME, user.username());
        }
    }

    private List<ConversationItem> mapConversationList(JsonNode node) {
        List<ConversationItem> items = new ArrayList<>();
        if (node == null || !node.isArray()) return items;
        node.forEach(n -> {
            ConversationItem item = new ConversationItem();
            item.setSessionId(text(n, "session_id"));
            item.setTitle(text(n, "title"));
            JsonNode mc = n.get("message_count");
            item.setMessageCount(mc != null && !mc.isNull() ? mc.asInt() : 0);
            item.setLastMessage(text(n, "last_message"));
            item.setCreatedAt(text(n, "created_at"));
            item.setUpdatedAt(text(n, "updated_at"));
            items.add(item);
        });
        return items;
    }

    private ConversationDetail mapConversationDetail(JsonNode node) {
        ConversationDetail detail = new ConversationDetail();
        detail.setSessionId(text(node, "session_id"));
        detail.setTitle(text(node, "title"));
        detail.setCreatedAt(text(node, "created_at"));
        List<ConversationDetail.ConversationMessage> msgs = new ArrayList<>();
        JsonNode arr = node.path("messages");
        if (arr.isArray()) {
            arr.forEach(m -> {
                ConversationDetail.ConversationMessage msg = new ConversationDetail.ConversationMessage();
                msg.setRole(text(m, "role"));
                msg.setContent(text(m, "content"));
                msg.setCreatedAt(text(m, "created_at"));
                msgs.add(msg);
            });
        }
        detail.setMessages(msgs);
        // Map snapshot if present
        JsonNode snapshot = node.get("snapshot");
        if (snapshot != null && !snapshot.isNull()) {
            ConversationDetail.ConversationSnapshot snap = new ConversationDetail.ConversationSnapshot();
            snap.setRiskLevel(text(snapshot, "risk_level"));
            snap.setQueryCount(integer(snapshot, "query_count"));
            JsonNode planInfo = snapshot.get("plan_info");
            if (planInfo != null && !planInfo.isNull() && planInfo.isObject()) {
                snap.setPlanInfo(planInfo);
            }
            JsonNode agentStatus = snapshot.get("agent_status_summary");
            if (agentStatus != null && !agentStatus.isNull() && agentStatus.isObject()) {
                snap.setAgentStatusSummary(agentStatus);
            }
            detail.setSnapshot(snap);
        }
        // Map hasMore for pagination
        JsonNode hasMore = node.get("has_more");
        if (hasMore != null && !hasMore.isNull()) {
            detail.setHasMore(hasMore.asBoolean(false));
        }
        return detail;
    }

    private ConversationDetail mapConversationFull(JsonNode node) {
        ConversationDetail detail = new ConversationDetail();
        // Map session
        JsonNode session = node.get("session");
        if (session != null && !session.isNull()) {
            detail.setSessionId(text(session, "session_id"));
            detail.setTitle(text(session, "title"));
            detail.setCreatedAt(text(session, "created_at"));
        }
        // Map snapshot if present
        JsonNode snapshot = node.get("snapshot");
        if (snapshot != null && !snapshot.isNull()) {
            ConversationDetail.ConversationSnapshot snap = new ConversationDetail.ConversationSnapshot();
            snap.setRiskLevel(text(snapshot, "risk_level"));
            snap.setQueryCount(integer(snapshot, "query_count"));
            JsonNode planInfo = snapshot.get("plan_info");
            if (planInfo != null && !planInfo.isNull() && planInfo.isObject()) {
                snap.setPlanInfo(planInfo);
            }
            JsonNode agentStatus = snapshot.get("agent_status_summary");
            if (agentStatus != null && !agentStatus.isNull() && agentStatus.isObject()) {
                snap.setAgentStatusSummary(agentStatus);
            }
            detail.setSnapshot(snap);
        }
        return detail;
    }

    private CreateConversationResponse mapCreateConversationResponse(JsonNode node) {
        CreateConversationResponse r = new CreateConversationResponse();
        r.setSessionId(text(node, "session_id"));
        r.setTitle(text(node, "title"));
        r.setCreatedAt(text(node, "created_at"));
        return r;
    }

    /**
     * Check if AI service is healthy
     */
    public Mono<Boolean> healthCheck() {
        return webClient.get()
                .uri("/docs")
                .retrieve()
                .toBodilessEntity()
                .map(response -> response.getStatusCode().is2xxSuccessful())
                .timeout(Duration.ofSeconds(properties.getConnectTimeoutSeconds()))
                .onErrorReturn(false);
    }

    private List<FloodPlanResponse> mapPlanList(JsonNode node) {
        List<FloodPlanResponse> plans = new ArrayList<>();
        if (node == null || !node.isArray()) {
            return plans;
        }
        node.forEach(item -> plans.add(mapPlanSummary(item)));
        return plans;
    }

    private FloodPlanResponse mapPlanSummary(JsonNode node) {
        FloodPlanResponse plan = new FloodPlanResponse();
        plan.setId(text(node, "plan_id", "id"));
        plan.setSessionId(text(node, "session_id", "sessionId"));
        plan.setRiskLevel(text(node, "risk_level", "riskLevel"));
        plan.setSummary(text(node, "summary"));
        plan.setStatus(text(node, "status"));
        plan.setCreatedAt(text(node, "created_at", "createdAt"));
        plan.setUpdatedAt(text(node, "updated_at", "updatedAt"));
        return plan;
    }

    private FloodPlanResponse mapPlanDetail(JsonNode node) {
        FloodPlanResponse plan = mapPlanSummary(node);
        plan.setActions(mapActions(node.path("actions")));
        plan.setResources(mapResources(node.path("resources")));
        plan.setNotifications(mapNotifications(node.path("notifications")));
        return plan;
    }

    private List<FloodPlanResponse.PlanAction> mapActions(JsonNode node) {
        List<FloodPlanResponse.PlanAction> actions = new ArrayList<>();
        if (node == null || !node.isArray()) {
            return actions;
        }
        node.forEach(item -> {
            FloodPlanResponse.PlanAction action = new FloodPlanResponse.PlanAction();
            action.setId(text(item, "action_id", "id"));
            action.setDescription(text(item, "description"));
            action.setPriority(text(item, "priority"));
            action.setAssignee(text(item, "responsible_dept", "assignee"));
            action.setStatus(text(item, "status"));
            action.setScheduledAt(text(item, "created_at", "scheduledAt"));
            actions.add(action);
        });
        return actions;
    }

    private List<FloodPlanResponse.PlanResource> mapResources(JsonNode node) {
        List<FloodPlanResponse.PlanResource> resources = new ArrayList<>();
        if (node == null || !node.isArray()) {
            return resources;
        }
        node.forEach(item -> {
            FloodPlanResponse.PlanResource resource = new FloodPlanResponse.PlanResource();
            resource.setId(text(item, "id"));
            resource.setType(text(item, "resource_type", "type"));
            resource.setName(text(item, "resource_name", "name"));
            resource.setQuantity(integer(item, "quantity"));
            resource.setLocation(firstNonBlank(
                    text(item, "target_location"),
                    text(item, "source_location"),
                    text(item, "location")
            ));
            resource.setStatus(text(item, "status"));
            resources.add(resource);
        });
        return resources;
    }

    private List<FloodPlanResponse.PlanNotification> mapNotifications(JsonNode node) {
        List<FloodPlanResponse.PlanNotification> notifications = new ArrayList<>();
        if (node == null || !node.isArray()) {
            return notifications;
        }
        node.forEach(item -> {
            FloodPlanResponse.PlanNotification notification = new FloodPlanResponse.PlanNotification();
            notification.setId(text(item, "id"));
            notification.setType(text(item, "type", "channel"));
            notification.setTarget(text(item, "target"));
            notification.setMessage(text(item, "content", "message"));
            notification.setStatus(text(item, "status"));
            notification.setSentAt(text(item, "sent_at", "sentAt"));
            notifications.add(notification);
        });
        return notifications;
    }

    private PlanExecuteResponse mapPlanExecuteResponse(JsonNode node) {
        PlanExecuteResponse response = new PlanExecuteResponse();
        response.setPlanId(text(node, "plan_id", "planId"));
        response.setStatus(text(node, "status"));
        response.setExecutedActions(integer(node, "executed_actions", "executedActions"));
        response.setMessage(text(node, "message"));
        return response;
    }

    private SessionResponse mapSessionResponse(JsonNode node) {
        SessionResponse response = new SessionResponse();
        response.setSessionId(text(node, "session_id", "sessionId"));
        response.setCreatedAt(text(node, "created_at", "createdAt"));
        response.setPlans(mapPlanList(node.path("plans")));
        return response;
    }

    private String text(JsonNode node, String... fieldNames) {
        if (node == null) {
            return null;
        }
        for (String fieldName : fieldNames) {
            JsonNode value = node.get(fieldName);
            if (value != null && !value.isNull()) {
                return value.asText();
            }
        }
        return null;
    }

    private Integer integer(JsonNode node, String... fieldNames) {
        if (node == null) {
            return null;
        }
        for (String fieldName : fieldNames) {
            JsonNode value = node.get(fieldName);
            if (value != null && !value.isNull()) {
                String textValue = value.asText();
                if (textValue == null || textValue.isBlank()) {
                    return null;
                }
                return value.isNumber() ? value.asInt() : Integer.parseInt(textValue);
            }
        }
        return null;
    }

    private String firstNonBlank(String... values) {
        for (String value : values) {
            if (value != null && !value.isBlank()) {
                return value;
            }
        }
        return null;
    }
}
