package com.waterinfo.platform.module.ai.client;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.waterinfo.platform.module.ai.config.AiServiceProperties;
import com.waterinfo.platform.module.ai.dto.FloodPlanResponse;
import com.waterinfo.platform.module.ai.dto.FloodQueryRequest;
import com.waterinfo.platform.module.ai.dto.FloodQueryResponse;
import com.waterinfo.platform.module.ai.dto.SessionResponse;
import jakarta.annotation.PostConstruct;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

import java.time.Duration;
import java.util.List;
import java.util.Map;

/**
 * AI service client for communicating with the Python AI service
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class AiServiceClient {

    private final AiServiceProperties properties;
    private final ObjectMapper objectMapper;

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
                .timeout(Duration.ofSeconds(properties.getTimeoutSeconds()))
                .doOnError(error -> log.error("Error calling AI service stream: {}", error.getMessage()));
    }

    /**
     * Get list of emergency plans
     */
    public Mono<Map<String, Object>> getPlans(int page, int size) {
        log.debug("Fetching plans from AI service, page: {}, size: {}", page, size);

        return webClient.get()
                .uri(uriBuilder -> uriBuilder
                        .path("/api/v1/plans")
                        .queryParam("page", page)
                        .queryParam("size", size)
                        .build())
                .retrieve()
                .bodyToMono(new ParameterizedTypeReference<Map<String, Object>>() {})
                .timeout(Duration.ofSeconds(properties.getTimeoutSeconds()))
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
                .bodyToMono(FloodPlanResponse.class)
                .timeout(Duration.ofSeconds(properties.getTimeoutSeconds()))
                .doOnError(error -> log.error("Error fetching plan {}: {}", id, error.getMessage()));
    }

    /**
     * Execute a plan
     */
    public Mono<FloodPlanResponse> executePlan(String id) {
        log.debug("Executing plan on AI service: {}", id);

        return webClient.post()
                .uri("/api/v1/plans/{id}/execute", id)
                .retrieve()
                .bodyToMono(FloodPlanResponse.class)
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
                .bodyToMono(SessionResponse.class)
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
}
