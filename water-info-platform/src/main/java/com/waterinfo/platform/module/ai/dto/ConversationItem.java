package com.waterinfo.platform.module.ai.dto;

import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;
import lombok.Data;

@Data
@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public class ConversationItem {
    private String sessionId;
    private String title;
    private Integer messageCount;
    private String lastMessage;
    private String createdAt;
    private String updatedAt;
}
