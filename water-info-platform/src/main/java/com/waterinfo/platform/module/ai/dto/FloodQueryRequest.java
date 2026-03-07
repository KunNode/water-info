package com.waterinfo.platform.module.ai.dto;

import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Data;

/**
 * Flood emergency query request DTO
 * Uses snake_case for JSON serialization to match Python AI service
 */
@Data
@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public class FloodQueryRequest {

    @NotBlank(message = "Query text is required")
    @Size(max = 2000, message = "Query must not exceed 2000 characters")
    private String query;

    @Size(max = 64, message = "Session ID must not exceed 64 characters")
    private String sessionId;
}
