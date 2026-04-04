package com.waterinfo.platform.module.ai.client;

import com.fasterxml.jackson.databind.JsonNode;
import com.waterinfo.platform.module.ai.config.AiServiceProperties;
import com.waterinfo.platform.module.ai.dto.FloodPlanPageResponse;
import com.waterinfo.platform.module.ai.dto.FloodPlanResponse;
import com.waterinfo.platform.module.ai.dto.FloodQueryRequest;
import com.waterinfo.platform.module.ai.dto.FloodQueryResponse;
import com.waterinfo.platform.module.ai.dto.PlanExecuteResponse;
import com.waterinfo.platform.module.ai.dto.SessionResponse;
import jakarta.annotation.PostConstruct;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

import java.time.Duration;
import java.util.ArrayList;
import java.util.List;

/**
 * AI service client for communicating with the Python AI service
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class AiServiceClient {

    private final AiServiceProperties properties;
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

        return webClient.post()
                .uri("/api/v1/flood/query")
                .bodyValue(request)
                .retrieve()
                .bodyToMono(FloodQueryResponse.class)
                .timeout(Duration.ofSeconds(properties.getTimeoutSeconds()))
                .doOnError(error -> log.error("Error calling AI service query: {}", error.getMessage()));
    }

    /**
     * Execute flood emergency query with streaming (SSE)
     */
    public Flux<String> queryFloodStream(FloodQueryRequest request) {
        log.debug("Sending flood stream query to AI service: {}", request.getQuery());

        return webClient.post()
                .uri("/api/v1/flood/query/stream")
                .header(HttpHeaders.ACCEPT, MediaType.TEXT_EVENT_STREAM_VALUE)
                .bodyValue(request)
                .retrieve()
                .bodyToFlux(String.class)
                .doOnError(error -> log.error("Error calling AI service stream: {}", error.getMessage()));
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

        return webClient.get()
                .uri("/api/v1/sessions/{id}", id)
                .retrieve()
                .bodyToMono(JsonNode.class)
                .map(this::mapSessionResponse)
                .timeout(Duration.ofSeconds(properties.getTimeoutSeconds()))
                .doOnError(error -> log.error("Error fetching session {}: {}", id, error.getMessage()));
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
