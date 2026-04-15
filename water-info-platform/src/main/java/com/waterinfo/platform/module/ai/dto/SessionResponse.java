package com.waterinfo.platform.module.ai.dto;

import lombok.Data;

import java.time.LocalDateTime;
import java.util.List;

/**
 * AI session history response DTO
 */
@Data
public class SessionResponse {

    private String id;
    private String status;
    private List<SessionMessage> messages;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;

    @Data
    public static class SessionMessage {
        private String role;
        private String content;
        private String agent;
        private LocalDateTime timestamp;
    }
}
