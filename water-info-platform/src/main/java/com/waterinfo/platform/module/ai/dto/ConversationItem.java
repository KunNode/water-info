package com.waterinfo.platform.module.ai.dto;

import lombok.Data;

@Data
public class ConversationItem {
    private String sessionId;
    private String title;
    private Integer messageCount;
    private String lastMessage;
    private String createdAt;
    private String updatedAt;
}
