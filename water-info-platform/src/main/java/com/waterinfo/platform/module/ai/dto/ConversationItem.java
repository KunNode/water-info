package com.waterinfo.platform.module.ai.dto;

import lombok.Data;

/**
 * Summary of a conversation session (used in list view).
 */
@Data
public class ConversationItem {
    private String sessionId;
    private String title;
    private Integer messageCount;
    private String lastMessage;
    private String createdAt;
    private String updatedAt;
}
