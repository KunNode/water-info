package com.waterinfo.platform.module.threshold.dto;

import lombok.Data;

import java.math.BigDecimal;

/**
 * Update threshold rule request DTO
 */
@Data
public class UpdateThresholdRuleRequest {

    private String level;
    private BigDecimal thresholdValue;
    private Integer durationMin;
    private BigDecimal rateThreshold;
}
