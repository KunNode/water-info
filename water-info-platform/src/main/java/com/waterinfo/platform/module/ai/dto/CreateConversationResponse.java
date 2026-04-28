package com.waterinfo.platform.module.ai.dto;

import lombok.Data;

@Data
public class CreateConversationResponse {
    private String sessionId;
    private String title;
    private String createdAt;
}
