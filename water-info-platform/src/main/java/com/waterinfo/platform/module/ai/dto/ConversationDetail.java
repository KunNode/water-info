package com.waterinfo.platform.module.ai.dto;

import com.fasterxml.jackson.databind.JsonNode;
import lombok.Data;

import java.util.List;

/**
 * Full conversation session with message history and business state snapshot.
 */
@Data
public class ConversationDetail {

    private String sessionId;
    private String title;
    private List<ConversationMessage> messages;
    private ConversationSnapshot snapshot;
    private boolean hasMore;
    private String createdAt;

    @Data
    public static class ConversationMessage {
        private Long id;
        private String role;
        private String content;
        private String messageType;
        private String status;
        private String createdAt;
    }

    /**
     * Business state snapshot for UI recovery.
     */
    @Data
    public static class ConversationSnapshot {
        private String riskLevel;
        private JsonNode planInfo;
        private JsonNode agentStatusSummary;
        private Integer queryCount;
    }
}
