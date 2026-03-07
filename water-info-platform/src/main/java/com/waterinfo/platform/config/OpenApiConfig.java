package com.waterinfo.platform.config;

import io.swagger.v3.oas.models.Components;
import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Contact;
import io.swagger.v3.oas.models.info.Info;
import io.swagger.v3.oas.models.security.SecurityRequirement;
import io.swagger.v3.oas.models.security.SecurityScheme;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springdoc.core.models.GroupedOpenApi;

/**
 * OpenAPI / Swagger configuration
 */
@Configuration
public class OpenApiConfig {

    private static final String SECURITY_SCHEME_NAME = "Bearer Authentication";

    @Bean
    public OpenAPI customOpenAPI() {
        return new OpenAPI()
                .info(new Info()
                        .title("Water Information Management System API")
                        .version("1.0.0")
                        .description("RESTful API for Water Information Management System - Base Platform")
                        .contact(new Contact()
                                .name("Water Info Team")
                                .email("support@waterinfo.com")))
                .addSecurityItem(new SecurityRequirement().addList(SECURITY_SCHEME_NAME))
                .components(new Components()
                        .addSecuritySchemes(SECURITY_SCHEME_NAME,
                                new SecurityScheme()
                                        .name(SECURITY_SCHEME_NAME)
                                        .type(SecurityScheme.Type.HTTP)
                                        .scheme("bearer")
                                        .bearerFormat("JWT")
                                        .description("Enter JWT token")));
    }

    /**
     * 全部接口（默认分组，包含所有 API）
     */
    @Bean
    public GroupedOpenApi allApi() {
        return group("00-all", "00-全部接口", "/api/**");
    }

    @Bean
    public GroupedOpenApi authApi() {
        return group("01-auth", "01-认证鉴权", "/api/v1/auth", "/api/v1/auth/**");
    }

    @Bean
    public GroupedOpenApi userAccessApi() {
        return GroupedOpenApi.builder()
                .group("02-user-access")
                .displayName("02-\u7528\u6237\u6743\u9650")
                .pathsToMatch(
                        "/api/v1/users",
                        "/api/v1/users/**",
                        "/api/v1/roles",
                        "/api/v1/roles/**",
                        "/api/v1/orgs",
                        "/api/v1/orgs/**",
                        "/api/v1/depts",
                        "/api/v1/depts/**"
                )
                .build();
    }

    @Bean
    public GroupedOpenApi stationApi() {
        return group("03-stations", "03-\u7ad9\u70b9\u7ba1\u7406", "/api/v1/stations", "/api/v1/stations/**");
    }

    @Bean
    public GroupedOpenApi sensorApi() {
        return group("04-sensors", "04-\u4f20\u611f\u5668\u7ba1\u7406", "/api/v1/sensors", "/api/v1/sensors/**");
    }

    @Bean
    public GroupedOpenApi observationApi() {
        return group("05-observations", "05-\u89c2\u6d4b\u6570\u636e", "/api/v1/observations", "/api/v1/observations/**");
    }

    @Bean
    public GroupedOpenApi thresholdApi() {
        return group("06-threshold-rules", "06-\u9608\u503c\u89c4\u5219", "/api/v1/threshold-rules", "/api/v1/threshold-rules/**");
    }

    @Bean
    public GroupedOpenApi alarmApi() {
        return group("07-alarms", "07-\u544a\u8b66\u7ba1\u7406", "/api/v1/alarms", "/api/v1/alarms/**");
    }

    @Bean
    public GroupedOpenApi auditApi() {
        return group("08-audit-logs", "08-\u5ba1\u8ba1\u65e5\u5fd7", "/api/v1/audit-logs", "/api/v1/audit-logs/**");
    }

    private GroupedOpenApi group(String groupId, String displayName, String... pathPatterns) {
        return GroupedOpenApi.builder()
                .group(groupId)
                .displayName(displayName)
                .pathsToMatch(pathPatterns)
                .build();
    }
}
