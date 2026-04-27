package com.waterinfo.platform.module.ai.dto;

import lombok.Data;

import java.util.List;

/**
 * Flood emergency plan response DTO
 */
@Data
public class FloodPlanResponse {

    private String id;
    private String sessionId;
    private String riskLevel;
    private String summary;
    private String status;
    private List<PlanAction> actions;
    private List<PlanResource> resources;
    private List<PlanNotification> notifications;
    private String createdAt;
    private String updatedAt;

    @Data
    public static class PlanAction {
        private String id;
        private String description;
        private String priority;
        private String assignee;
        private String status;
        private String scheduledAt;
    }

    @Data
    public static class PlanResource {
        private String id;
        private String type;
        private String name;
        private Integer quantity;
        private String location;
        private String status;
    }

    @Data
    public static class PlanNotification {
        private String id;
        private String type;
        private String target;
        private String message;
        private String status;
        private String sentAt;
    }
}
