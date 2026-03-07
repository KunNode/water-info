package com.waterinfo.platform.config;

import jakarta.servlet.*;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.web.servlet.FilterRegistrationBean;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.annotation.Order;
import org.springframework.http.HttpStatus;

import java.io.IOException;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * Rate limiting configuration
 */
@Slf4j
@Configuration
public class RateLimitConfig {

    @Value("${ratelimit.enabled:true}")
    private boolean rateLimitEnabled;

    private final Map<String, RateLimitBucket> buckets = new ConcurrentHashMap<>();

    @Bean
    @Order(2)
    public FilterRegistrationBean<Filter> rateLimitFilter() {
        FilterRegistrationBean<Filter> registration = new FilterRegistrationBean<>();
        registration.setFilter(new RateLimitFilter());
        registration.addUrlPatterns("/api/*");
        registration.setName("rateLimitFilter");
        registration.setEnabled(rateLimitEnabled);
        return registration;
    }

    /**
     * Rate limit filter implementation
     */
    private class RateLimitFilter implements Filter {

        @Override
        public void doFilter(ServletRequest request, ServletResponse response, FilterChain chain)
                throws IOException, ServletException {

            HttpServletRequest httpRequest = (HttpServletRequest) request;
            HttpServletResponse httpResponse = (HttpServletResponse) response;

            String uri = httpRequest.getRequestURI();
            String clientId = getClientId(httpRequest);

            // Get rate limit config for this endpoint
            RateLimitRule config = getConfig(uri);
            if (config == null) {
                chain.doFilter(request, response);
                return;
            }

            String bucketKey = clientId + ":" + uri;
            RateLimitBucket bucket = buckets.computeIfAbsent(bucketKey,
                    k -> new RateLimitBucket(config.limit, config.windowSeconds));

            if (!bucket.tryConsume()) {
                log.warn("Rate limit exceeded: client={}, uri={}", clientId, uri);
                httpResponse.setStatus(HttpStatus.TOO_MANY_REQUESTS.value());
                httpResponse.setContentType("application/json");
                httpResponse.getWriter().write("{\"code\":429,\"message\":\"Rate limit exceeded. Please try again later.\"}");
                return;
            }

            // Add rate limit headers
            httpResponse.setHeader("X-RateLimit-Limit", String.valueOf(config.limit));
            httpResponse.setHeader("X-RateLimit-Remaining", String.valueOf(bucket.getRemaining()));
            httpResponse.setHeader("X-RateLimit-Reset", String.valueOf(bucket.getResetTime()));

            chain.doFilter(request, response);
        }

        private String getClientId(HttpServletRequest request) {
            // Use IP address as client identifier
            String xff = request.getHeader("X-Forwarded-For");
            if (xff != null && !xff.isEmpty()) {
                return xff.split(",")[0].trim();
            }
            return request.getRemoteAddr();
        }

        private RateLimitRule getConfig(String uri) {
            // Default rate limit
            return new RateLimitRule(100, 60);
        }
    }

    /**
     * Rate limit bucket
     */
    private static class RateLimitBucket {
        private final int limit;
        private final int windowSeconds;
        private final AtomicInteger count = new AtomicInteger(0);
        private volatile long resetTime;

        public RateLimitBucket(int limit, int windowSeconds) {
            this.limit = limit;
            this.windowSeconds = windowSeconds;
            this.resetTime = System.currentTimeMillis() + (windowSeconds * 1000L);
        }

        public synchronized boolean tryConsume() {
            if (System.currentTimeMillis() > resetTime) {
                // Reset bucket
                count.set(0);
                resetTime = System.currentTimeMillis() + (windowSeconds * 1000L);
            }

            if (count.get() < limit) {
                count.incrementAndGet();
                return true;
            }
            return false;
        }

        public int getRemaining() {
            return Math.max(0, limit - count.get());
        }

        public long getResetTime() {
            return resetTime / 1000;
        }
    }

    /**
     * Rate limit rule
     */
    private static class RateLimitRule {
        private final int limit;
        private final int windowSeconds;

        public RateLimitRule(int limit, int windowSeconds) {
            this.limit = limit;
            this.windowSeconds = windowSeconds;
        }
    }
}
