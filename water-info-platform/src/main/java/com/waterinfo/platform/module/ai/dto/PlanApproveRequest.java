package com.waterinfo.platform.module.ai.dto;

import jakarta.validation.constraints.NotNull;
import lombok.Data;

/**
 * Request DTO for approving a draft plan (POST /api/v1/plans/{id}/approve).
 */
@Data
public class PlanApproveRequest {

    @NotNull(message = "version is required")
    private Integer version;

    private String opinion;
}
