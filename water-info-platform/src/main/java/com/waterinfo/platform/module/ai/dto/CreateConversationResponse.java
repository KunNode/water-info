package com.waterinfo.platform.module.ai.dto;

import lombok.Data;

/**
 * Response returned after creating a new conversation session.
 */
@Data
public class CreateConversationResponse {
    private String sessionId;
    private String title;
    private String createdAt;
}
