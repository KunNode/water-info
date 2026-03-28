package com.waterinfo.platform.common.util;

import org.slf4j.MDC;

import java.util.UUID;

/**
 * Utility class for trace ID generation and management
 */
public final class TraceIdUtil {

    public static final String TRACE_ID_KEY = "traceId";

    private TraceIdUtil() {
        // Utility class
    }

    /**
     * Generate a new trace ID
     */
    public static String generateTraceId() {
        return UUID.randomUUID().toString().replace("-", "").substring(0, 16);
    }

    /**
     * Set trace ID in MDC
     */
    public static void setTraceId(String traceId) {
        MDC.put(TRACE_ID_KEY, traceId);
    }

    /**
     * Get trace ID from MDC
     */
    public static String getTraceId() {
        return MDC.get(TRACE_ID_KEY);
    }

    /**
     * Remove trace ID from MDC
     */
    public static void removeTraceId() {
        MDC.remove(TRACE_ID_KEY);
    }

    /**
     * Clear all MDC entries
     */
    public static void clear() {
        MDC.clear();
    }
}
