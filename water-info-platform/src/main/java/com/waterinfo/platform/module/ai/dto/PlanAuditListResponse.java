package com.waterinfo.platform.module.ai.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Data;

import java.util.List;

/**
 * Response DTO for GET /api/v1/plans/{id}/audits.
 */
@Data
public class PlanAuditListResponse {

    @JsonProperty("plan_id")
    private String planId;

    private List<PlanAuditRecord> records;
}
