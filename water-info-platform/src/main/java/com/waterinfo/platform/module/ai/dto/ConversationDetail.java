package com.waterinfo.platform.module.ai.dto;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;
import lombok.Data;

import java.util.List;

@Data
@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public class ConversationDetail {

    private String sessionId;
    private String title;
    private List<ConversationMessage> messages;
    private ConversationSnapshot snapshot;
    private boolean hasMore;
    private String createdAt;

    @Data
    @JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
    public static class ConversationMessage {
        private Long id;
        private String role;
        private String content;
        private String messageType;
        private String status;
        private JsonNode metadata;
        private String createdAt;
    }

    @Data
    @JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
    public static class ConversationSnapshot {
        private String riskLevel;
        private JsonNode planInfo;
        private JsonNode agentStatusSummary;
        private Integer queryCount;
    }
}
