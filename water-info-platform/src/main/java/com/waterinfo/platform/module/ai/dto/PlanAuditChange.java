package com.waterinfo.platform.module.ai.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Data;

/**
 * DTO representing a single field-level change within an audit record.
 */
@Data
public class PlanAuditChange {

    private Long id;

    @JsonProperty("audit_id")
    private Long auditId;

    @JsonProperty("field_path")
    private String fieldPath;

    @JsonProperty("change_type")
    private String changeType;

    @JsonProperty("old_value")
    private String oldValue;

    @JsonProperty("new_value")
    private String newValue;

    @JsonProperty("old_index")
    private Integer oldIndex;

    @JsonProperty("new_index")
    private Integer newIndex;
}
