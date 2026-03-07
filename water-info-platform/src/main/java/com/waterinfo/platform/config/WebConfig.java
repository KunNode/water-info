package com.waterinfo.platform.config;

import com.waterinfo.platform.common.api.ApiResponse;
import com.waterinfo.platform.common.util.TraceIdUtil;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.filter.OncePerRequestFilter;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

import java.io.IOException;

/**
 * Web MVC configuration
 */
@Configuration
public class WebConfig implements WebMvcConfigurer {

    @Override
    public void addCorsMappings(CorsRegistry registry) {
        registry.addMapping("/api/**")
                .allowedOriginPatterns("*")
                .allowedMethods("GET", "POST", "PUT", "DELETE", "OPTIONS")
                .allowedHeaders("*")
                .allowCredentials(true)
                .maxAge(3600);
        // Swagger / Knife4j 跨域支持
        registry.addMapping("/v3/api-docs/**")
                .allowedOriginPatterns("*")
                .allowedMethods("GET")
                .allowedHeaders("*");
        registry.addMapping("/swagger-resources/**")
                .allowedOriginPatterns("*")
                .allowedMethods("GET")
                .allowedHeaders("*");
    }

    /**
     * Filter to generate and manage trace ID for each request
     */
    @Bean
    public OncePerRequestFilter traceIdFilter() {
        return new OncePerRequestFilter() {
            @Override
            protected void doFilterInternal(HttpServletRequest request,
                                            HttpServletResponse response,
                                            FilterChain filterChain) throws ServletException, IOException {
                try {
                    // Generate or extract trace ID
                    String traceId = request.getHeader("X-Trace-Id");
                    if (traceId == null || traceId.isEmpty()) {
                        traceId = TraceIdUtil.generateTraceId();
                    }
                    
                    // Set trace ID in MDC and response holder
                    TraceIdUtil.setTraceId(traceId);
                    ApiResponse.TraceIdHolder.setTraceId(traceId);
                    
                    // Add trace ID to response header
                    response.setHeader("X-Trace-Id", traceId);
                    
                    filterChain.doFilter(request, response);
                } finally {
                    // Clean up
                    TraceIdUtil.removeTraceId();
                    ApiResponse.TraceIdHolder.clear();
                }
            }
        };
    }
}
