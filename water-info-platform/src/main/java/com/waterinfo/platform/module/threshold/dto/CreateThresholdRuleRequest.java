package com.waterinfo.platform.module.threshold.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Data;

import java.math.BigDecimal;

/**
 * Create threshold rule request DTO
 */
@Data
public class CreateThresholdRuleRequest {

    @NotBlank(message = "Station ID is required")
    private String stationId;

    @NotBlank(message = "Metric type is required")
    private String metricType;

    @NotBlank(message = "Level is required")
    private String level;

    @NotNull(message = "Threshold value is required")
    private BigDecimal thresholdValue;

    private Integer durationMin;

    private BigDecimal rateThreshold;
}
