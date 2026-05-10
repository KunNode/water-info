package com.waterinfo.platform.config;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.extern.slf4j.Slf4j;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;
import org.springframework.web.util.ContentCachingResponseWrapper;

import java.io.IOException;

/**
 * Logs HTTP request/response summary for every API call.
 */
@Slf4j
@Component
@Order(Ordered.HIGHEST_PRECEDENCE + 10)
public class RequestLoggingFilter extends OncePerRequestFilter {

    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                    HttpServletResponse response,
                                    FilterChain filterChain) throws ServletException, IOException {
        if (shouldSkip(request)) {
            filterChain.doFilter(request, response);
            return;
        }

        long start = System.currentTimeMillis();

        // Reactive endpoints (returning Mono/Flux) must NOT be wrapped —
        // the async write bypasses ContentCachingResponseWrapper, producing
        // an empty response body.
        if (isReactiveEndpoint(request.getRequestURI())) {
            try {
                filterChain.doFilter(request, response);
            } finally {
                logDuration(request, response.getStatus(), start);
            }
            return;
        }

        ContentCachingResponseWrapper wrappedResponse = new ContentCachingResponseWrapper(response);
        try {
            filterChain.doFilter(request, wrappedResponse);
        } finally {
            logDuration(request, wrappedResponse.getStatus(), start);
            wrappedResponse.copyBodyToResponse();
        }
    }

    private void logDuration(HttpServletRequest request, int status, long start) {
        long duration = System.currentTimeMillis() - start;
        if (status >= 500) {
            log.error("HTTP {} {} {} {}ms", request.getMethod(), request.getRequestURI(), status, duration);
        } else if (status >= 400) {
            log.warn("HTTP {} {} {} {}ms", request.getMethod(), request.getRequestURI(), status, duration);
        } else {
            log.info("HTTP {} {} {} {}ms", request.getMethod(), request.getRequestURI(), status, duration);
        }
    }

    /**
     * Endpoints that return reactive types (Mono/Flux) must not be wrapped
     * with ContentCachingResponseWrapper — the async response write bypasses
     * the wrapper, resulting in an empty response body.
     */
    private boolean isReactiveEndpoint(String uri) {
        return uri.startsWith("/api/v1/flood/")
                || uri.startsWith("/api/v1/plans")
                || uri.startsWith("/api/v1/sessions")
                || uri.startsWith("/api/v1/conversations")
                || uri.startsWith("/api/v1/kb/");
    }

    private boolean shouldSkip(HttpServletRequest request) {
        String uri = request.getRequestURI();
        return uri.startsWith("/actuator")
                || uri.equals("/api/v1/flood/query/stream")
                || uri.startsWith("/ws/")
                || uri.startsWith("/swagger")
                || uri.startsWith("/v3/api-docs")
                || uri.startsWith("/doc.html")
                || uri.startsWith("/webjars")
                || uri.equals("/favicon.ico");
    }
}
