package com.waterinfo.platform.module.ai.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import lombok.Data;

import java.util.List;

/**
 * Request DTO for editing a plan's content (PATCH /api/v1/plans/{id}).
 * All fields except version are optional; only submit the sections that need modification.
 */
@Data
public class PlanEditRequest {

    @NotNull(message = "version is required")
    private Integer version;

    @Size(max = 50000, message = "summary must not exceed 50000 characters")
    private String summary;

    private ActionsPatch actions;

    private ResourcesPatch resources;

    private NotificationsPatch notifications;

    @Data
    public static class ActionsPatch {
        private List<ActionUpsert> upsert;
        private List<String> delete;
    }

    @Data
    public static class ActionUpsert {
        @JsonProperty("actionId")
        private String actionId;

        private String description;
        private Integer priority;
        private String assignee;
        private String status;
    }

    @Data
    public static class ResourcesPatch {
        private List<ResourceUpsert> upsert;
        private List<Integer> delete;
    }

    @Data
    public static class ResourceUpsert {
        @JsonProperty("resourceId")
        private Integer resourceId;

        private String type;
        private String name;
        private Integer quantity;
        private String location;
    }

    @Data
    public static class NotificationsPatch {
        private List<NotificationUpsert> upsert;
        private List<Integer> delete;
    }

    @Data
    public static class NotificationUpsert {
        @JsonProperty("notificationId")
        private Integer notificationId;

        private String channel;
        private String target;
        private String message;
        private String status;
    }
}
