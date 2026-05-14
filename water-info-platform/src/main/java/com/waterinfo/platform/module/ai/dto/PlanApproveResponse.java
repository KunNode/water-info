package com.waterinfo.platform.module.ai.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Data;

/**
 * Response DTO for a successful plan approval (POST /api/v1/plans/{id}/approve).
 */
@Data
public class PlanApproveResponse {

    @JsonProperty("plan_id")
    private String planId;

    private String status;

    private int version;

    @JsonProperty("audit_record_id")
    private long auditRecordId;
}
