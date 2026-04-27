package com.waterinfo.platform.module.ai.dto;

import lombok.Data;

import java.util.List;

/**
 * AI session history response DTO
 */
@Data
public class SessionResponse {

    private String sessionId;
    private List<FloodPlanResponse> plans;
    private String createdAt;
}
