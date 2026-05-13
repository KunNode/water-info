package com.waterinfo.platform.module.ai.client;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import com.waterinfo.platform.module.ai.config.AiServiceProperties;
import com.waterinfo.platform.module.ai.context.AiUserContext;
import com.waterinfo.platform.module.ai.dto.PlanApproveRequest;
import com.waterinfo.platform.module.ai.dto.PlanEditRequest;
import com.waterinfo.platform.security.SecurityUser;
import org.junit.jupiter.api.*;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.ReactiveSecurityContextHolder;
import org.springframework.security.core.context.SecurityContextHolder;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CopyOnWriteArrayList;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Integration test verifying that AiServiceClient propagates X-User-Id and X-Username
 * headers from the authenticated SecurityUser to the downstream Python service.
 *
 * Uses JDK HttpServer to capture outbound requests and assert header values.
 *
 * Validates: Requirements 8.1
 * Properties: P5
 */
class AiServiceClientIdentityHeadersTest {

    private static HttpServer server;
    private static int port;
    private static final List<CapturedRequest> capturedRequests = new CopyOnWriteArrayList<>();

    private AiServiceClient client;
    private Authentication authentication;

    private static final String TEST_USER_ID = "u-42";
    private static final String TEST_USERNAME = "reviewer_zhang";

    record CapturedRequest(String method, String path, Map<String, List<String>> headers) {}

    @BeforeAll
    static void startServer() throws IOException {
        server = HttpServer.create(new InetSocketAddress(0), 0);
        port = server.getAddress().getPort();

        // Catch-all handler that records requests and returns a valid JSON response
        server.createContext("/", exchange -> {
            capturedRequests.add(new CapturedRequest(
                    exchange.getRequestMethod(),
                    exchange.getRequestURI().getPath(),
                    exchange.getRequestHeaders()
            ));
            // Drain request body
            exchange.getRequestBody().readAllBytes();

            String responseBody = buildResponse(exchange);
            byte[] bytes = responseBody.getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().set("Content-Type", "application/json");
            exchange.sendResponseHeaders(200, bytes.length);
            try (OutputStream os = exchange.getResponseBody()) {
                os.write(bytes);
            }
        });
        server.start();
    }

    @AfterAll
    static void stopServer() {
        server.stop(0);
    }

    @BeforeEach
    void setUp() {
        capturedRequests.clear();

        // Configure AiServiceProperties to point to our embedded server
        AiServiceProperties properties = new AiServiceProperties();
        properties.setUrl("http://localhost:" + port);
        properties.setTimeoutSeconds(5);
        properties.setConnectTimeoutSeconds(5);

        AiUserContext userContext = new AiUserContext();
        ObjectMapper objectMapper = new ObjectMapper();

        client = new AiServiceClient(properties, userContext, objectMapper);
        client.init();

        // Set up SecurityContext with a known SecurityUser
        SecurityUser securityUser = SecurityUser.builder()
                .id(TEST_USER_ID)
                .username(TEST_USERNAME)
                .roles(List.of("OPERATOR"))
                .enabled(true)
                .accountNonLocked(true)
                .build();
        authentication = new UsernamePasswordAuthenticationToken(
                securityUser, null, securityUser.getAuthorities());
        SecurityContextHolder.getContext().setAuthentication(authentication);
    }

    @AfterEach
    void tearDown() {
        SecurityContextHolder.clearContext();
    }

    @Test
    @DisplayName("updatePlan propagates X-User-Id and X-Username headers")
    void updatePlan_propagatesIdentityHeaders() {
        PlanEditRequest request = new PlanEditRequest();
        request.setVersion(0);

        // Subscribe with reactive security context so AiUserContext.getCurrentUser() resolves
        client.updatePlan("plan-001", request)
                .contextWrite(ReactiveSecurityContextHolder.withAuthentication(authentication))
                .block();

        assertThat(capturedRequests).hasSize(1);
        CapturedRequest captured = capturedRequests.get(0);
        assertThat(captured.method()).isEqualTo("PATCH");
        assertThat(captured.path()).isEqualTo("/api/v1/plans/plan-001");
        assertIdentityHeaders(captured);
    }

    @Test
    @DisplayName("approvePlan propagates X-User-Id and X-Username headers")
    void approvePlan_propagatesIdentityHeaders() {
        PlanApproveRequest request = new PlanApproveRequest();
        request.setVersion(1);
        request.setOpinion("同意执行");

        client.approvePlan("plan-002", request)
                .contextWrite(ReactiveSecurityContextHolder.withAuthentication(authentication))
                .block();

        assertThat(capturedRequests).hasSize(1);
        CapturedRequest captured = capturedRequests.get(0);
        assertThat(captured.method()).isEqualTo("POST");
        assertThat(captured.path()).isEqualTo("/api/v1/plans/plan-002/approve");
        assertIdentityHeaders(captured);
    }

    @Test
    @DisplayName("listPlanAudits propagates X-User-Id and X-Username headers")
    void listPlanAudits_propagatesIdentityHeaders() {
        client.listPlanAudits("plan-003")
                .contextWrite(ReactiveSecurityContextHolder.withAuthentication(authentication))
                .block();

        assertThat(capturedRequests).hasSize(1);
        CapturedRequest captured = capturedRequests.get(0);
        assertThat(captured.method()).isEqualTo("GET");
        assertThat(captured.path()).isEqualTo("/api/v1/plans/plan-003/audits");
        assertIdentityHeaders(captured);
    }

    /**
     * Assert that the captured request has valid X-User-Id and X-Username headers
     * matching the SecurityUser's current values.
     */
    private void assertIdentityHeaders(CapturedRequest captured) {
        String userId = getHeader(captured, AiUserContext.HEADER_USER_ID);
        String username = getHeader(captured, AiUserContext.HEADER_USERNAME);

        // Non-empty
        assertThat(userId).as("X-User-Id must be non-empty").isNotNull().isNotEmpty();
        assertThat(username).as("X-Username must be non-empty").isNotNull().isNotEmpty();

        // Length ≤ 255
        assertThat(userId.length()).as("X-User-Id length must be ≤ 255").isLessThanOrEqualTo(255);
        assertThat(username.length()).as("X-Username length must be ≤ 255").isLessThanOrEqualTo(255);

        // Match SecurityUser's values
        assertThat(userId).as("X-User-Id must equal SecurityUser.id").isEqualTo(TEST_USER_ID);
        assertThat(username).as("X-Username must equal SecurityUser.username").isEqualTo(TEST_USERNAME);
    }

    private static String getHeader(CapturedRequest request, String headerName) {
        // JDK HttpServer normalizes header names to Title-Case
        List<String> values = request.headers().get(headerName);
        if (values == null || values.isEmpty()) return null;
        return values.get(0);
    }

    /**
     * Build a minimal valid JSON response based on the request path.
     */
    private static String buildResponse(HttpExchange exchange) {
        String path = exchange.getRequestURI().getPath();
        if (path.endsWith("/approve")) {
            return "{\"planId\":\"plan-002\",\"status\":\"approved\",\"version\":2,\"auditRecordId\":100}";
        } else if (path.endsWith("/audits")) {
            return "{\"planId\":\"plan-003\",\"records\":[]}";
        } else {
            // Default: plan detail response for PATCH
            return "{\"plan_id\":\"plan-001\",\"status\":\"draft\",\"version\":1,"
                    + "\"summary\":\"\",\"actions\":[],\"resources\":[],\"notifications\":[]}";
        }
    }
}
