package com.waterinfo.platform.module.ai.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Data;

import java.util.List;

/**
 * DTO representing a single audit record for a plan review action.
 */
@Data
public class PlanAuditRecord {

    private Long id;

    private String action;

    @JsonProperty("reviewer_user_id")
    private String reviewerUserId;

    @JsonProperty("reviewer_username")
    private String reviewerUsername;

    @JsonProperty("reviewed_at")
    private String reviewedAt;

    private String opinion;

    @JsonProperty("from_status")
    private String fromStatus;

    @JsonProperty("to_status")
    private String toStatus;

    @JsonProperty("from_version")
    private Integer fromVersion;

    @JsonProperty("to_version")
    private Integer toVersion;

    private List<PlanAuditChange> changes;
}
