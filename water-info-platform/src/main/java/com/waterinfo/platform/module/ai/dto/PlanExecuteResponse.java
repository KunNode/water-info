package com.waterinfo.platform.module.ai.dto;

import lombok.Data;

@Data
public class PlanExecuteResponse {
    private String planId;
    private String status;
    private int executedActions;
    private String message;
}
