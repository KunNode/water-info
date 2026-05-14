package com.waterinfo.platform.module.ai.controller;

import com.github.tomakehurst.wiremock.WireMockServer;
import com.github.tomakehurst.wiremock.client.WireMock;
import com.github.tomakehurst.wiremock.core.WireMockConfiguration;
import org.junit.jupiter.api.*;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.MethodSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

import java.util.stream.Stream;

import static com.github.tomakehurst.wiremock.client.WireMock.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * Authorization matrix test for FloodAiController plan review endpoints.
 * <p>
 * Table-driven: for (role ∈ {ANON, VIEWER, OPERATOR, ADMIN}) × (endpoint ∈ {edit, approve, audits})
 * asserts 200/401/403. WireMock mocks Python responses as 200 to isolate authorization logic.
 * <p>
 * Validates: Requirements 2.2, 2.5, 5.1, 5.2, 5.3, 5.5, 7.6, 9.2, 9.3
 * Properties: P2
 */
@SpringBootTest
@AutoConfigureMockMvc
@Testcontainers
@ActiveProfiles("test")
class FloodAiControllerAuthMatrixTest {

    @Container
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:15-alpine")
            .withDatabaseName("water_info_test")
            .withUsername("test")
            .withPassword("test");

    static WireMockServer wireMock;

    static {
        wireMock = new WireMockServer(WireMockConfiguration.wireMockConfig().dynamicPort());
        wireMock.start();
    }

    @Autowired
    private MockMvc mockMvc;

    @AfterAll
    static void stopWireMock() {
        wireMock.stop();
    }

    @DynamicPropertySource
    static void configureProperties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", postgres::getJdbcUrl);
        registry.add("spring.datasource.username", postgres::getUsername);
        registry.add("spring.datasource.password", postgres::getPassword);
        registry.add("ai.service.url", () -> "http://localhost:" + wireMock.port());
    }

    @BeforeEach
    void setupWireMockStubs() {
        wireMock.resetAll();

        // Stub POST /api/v1/plans/{id}/approve → 200 (register before generic PATCH to avoid conflicts)
        wireMock.stubFor(WireMock.post(urlPathMatching("/api/v1/plans/[^/]+/approve"))
                .willReturn(aResponse()
                        .withStatus(200)
                        .withHeader("Content-Type", "application/json")
                        .withBody(approveResponseJson())));

        // Stub GET /api/v1/plans/{id}/audits → 200
        wireMock.stubFor(WireMock.get(urlPathMatching("/api/v1/plans/[^/]+/audits"))
                .willReturn(aResponse()
                        .withStatus(200)
                        .withHeader("Content-Type", "application/json")
                        .withBody(auditListJson())));

        // Stub PATCH /api/v1/plans/{id} → 200 with a minimal valid plan response
        wireMock.stubFor(WireMock.patch(urlPathMatching("/api/v1/plans/[^/]+"))
                .willReturn(aResponse()
                        .withStatus(200)
                        .withHeader("Content-Type", "application/json")
                        .withBody(planDetailJson())));
    }

    // ── Table-driven parameterized test ─────────────────────────────────────

    @ParameterizedTest(name = "{0} → {1} expects {2}")
    @MethodSource("authMatrix")
    void authorizationMatrix(String role, String endpoint, int expectedStatus) throws Exception {
        MockHttpServletRequestBuilder request = buildRequest(endpoint);

        if (!"ANON".equals(role)) {
            request.with(SecurityMockMvcRequestPostProcessors.user("testuser")
                    .roles(role));
        }

        MvcResult mvcResult = mockMvc.perform(request)
                .andReturn();

        // Handle async dispatch for Mono-returning controllers
        if (mvcResult.getRequest().isAsyncStarted()) {
            mockMvc.perform(asyncDispatch(mvcResult))
                    .andExpect(status().is(expectedStatus));
        } else {
            Assertions.assertEquals(expectedStatus, mvcResult.getResponse().getStatus(),
                    String.format("Expected %d for role=%s endpoint=%s but got %d",
                            expectedStatus, role, endpoint, mvcResult.getResponse().getStatus()));
        }
    }

    static Stream<Arguments> authMatrix() {
        return Stream.of(
                // ANON (unauthenticated) → 401 for all endpoints
                Arguments.of("ANON", "edit", 401),
                Arguments.of("ANON", "approve", 401),
                Arguments.of("ANON", "audits", 401),

                // VIEWER → 403 for edit/approve, 200 for audits
                Arguments.of("VIEWER", "edit", 403),
                Arguments.of("VIEWER", "approve", 403),
                Arguments.of("VIEWER", "audits", 200),

                // OPERATOR → 200 for all
                Arguments.of("OPERATOR", "edit", 200),
                Arguments.of("OPERATOR", "approve", 200),
                Arguments.of("OPERATOR", "audits", 200),

                // ADMIN → 200 for all
                Arguments.of("ADMIN", "edit", 200),
                Arguments.of("ADMIN", "approve", 200),
                Arguments.of("ADMIN", "audits", 200)
        );
    }

    // ── Helpers ─────────────────────────────────────────────────────────────

    private MockHttpServletRequestBuilder buildRequest(String endpoint) {
        String planId = "test-plan-001";
        return switch (endpoint) {
            case "edit" -> patch("/api/v1/plans/" + planId)
                    .contentType(MediaType.APPLICATION_JSON)
                    .content(editRequestJson());
            case "approve" -> post("/api/v1/plans/" + planId + "/approve")
                    .contentType(MediaType.APPLICATION_JSON)
                    .content(approveRequestJson());
            case "audits" -> get("/api/v1/plans/" + planId + "/audits");
            default -> throw new IllegalArgumentException("Unknown endpoint: " + endpoint);
        };
    }

    private String editRequestJson() {
        return """
                {
                  "version": 1,
                  "summary": "Test summary"
                }
                """;
    }

    private String approveRequestJson() {
        return """
                {
                  "version": 1,
                  "opinion": "Approved for testing"
                }
                """;
    }

    private static String planDetailJson() {
        return """
                {
                  "plan_id": "test-plan-001",
                  "title": "Test Plan",
                  "status": "draft",
                  "summary": "Test summary",
                  "version": 2,
                  "actions": [],
                  "resources": [],
                  "notifications": []
                }
                """;
    }

    private static String approveResponseJson() {
        return """
                {
                  "plan_id": "test-plan-001",
                  "status": "approved",
                  "version": 2,
                  "audit_record_id": 1
                }
                """;
    }

    private static String auditListJson() {
        return """
                {
                  "plan_id": "test-plan-001",
                  "records": []
                }
                """;
    }
}
