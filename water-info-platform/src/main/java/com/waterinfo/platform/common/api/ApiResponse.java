package com.waterinfo.platform.common.api;

import com.fasterxml.jackson.annotation.JsonInclude;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;
import java.util.Map;

/**
 * Unified API Response wrapper
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@JsonInclude(JsonInclude.Include.NON_NULL)
public class ApiResponse<T> implements Serializable {

    private static final long serialVersionUID = 1L;

    private Integer code;
    private String message;
    private T data;
    private String traceId;
    private Long timestamp;
    private Pagination pagination;
    private Map<String, Object> metadata;

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class Pagination implements Serializable {
        private Integer page;
        private Integer size;
        private Long total;
        private Integer pages;
    }

    public static <T> ApiResponse<T> success() {
        return success(null);
    }

    public static <T> ApiResponse<T> success(T data) {
        return ApiResponse.<T>builder()
                .code(200)
                .message("success")
                .data(data)
                .traceId(TraceIdHolder.getTraceId())
                .timestamp(System.currentTimeMillis())
                .build();
    }

    public static <T> ApiResponse<T> success(String message, T data) {
        return ApiResponse.<T>builder()
                .code(200)
                .message(message)
                .data(data)
                .traceId(TraceIdHolder.getTraceId())
                .timestamp(System.currentTimeMillis())
                .build();
    }

    public static <T> ApiResponse<T> successPage(T data, int page, int size, long total) {
        int pages = size > 0 ? (int) Math.ceil((double) total / size) : 0;
        return ApiResponse.<T>builder()
                .code(200)
                .message("success")
                .data(data)
                .pagination(Pagination.builder()
                        .page(page)
                        .size(size)
                        .total(total)
                        .pages(pages)
                        .build())
                .traceId(TraceIdHolder.getTraceId())
                .timestamp(System.currentTimeMillis())
                .build();
    }

    public static <T> ApiResponse<T> error(Integer code, String message) {
        return ApiResponse.<T>builder()
                .code(code)
                .message(message)
                .traceId(TraceIdHolder.getTraceId())
                .timestamp(System.currentTimeMillis())
                .build();
    }

    public static <T> ApiResponse<T> error(Integer code, String message, T data) {
        return ApiResponse.<T>builder()
                .code(code)
                .message(message)
                .data(data)
                .traceId(TraceIdHolder.getTraceId())
                .timestamp(System.currentTimeMillis())
                .build();
    }

    /**
     * Thread-local holder for trace ID
     */
    public static class TraceIdHolder {
        private static final ThreadLocal<String> TRACE_ID = new ThreadLocal<>();

        public static void setTraceId(String traceId) {
            TRACE_ID.set(traceId);
        }

        public static String getTraceId() {
            return TRACE_ID.get();
        }

        public static void clear() {
            TRACE_ID.remove();
        }
    }
}
