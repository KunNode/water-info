package com.waterinfo.platform.module.ai.dto;

import lombok.Data;

import java.time.LocalDateTime;
import java.util.List;

/**
 * Flood emergency query response DTO
 */
@Data
public class FloodQueryResponse {

    private String sessionId;
    private String response;
    private String riskLevel;
    private List<AgentMessage> messages;
    private LocalDateTime timestamp;

    @Data
    public static class AgentMessage {
        private String agent;
        private String content;
        private LocalDateTime timestamp;
    }
}
