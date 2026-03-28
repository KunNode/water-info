package com.waterinfo.platform.module.observation.vo;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * Observation view object
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ObservationVO {

    private String id;
    private String stationId;
    private String stationCode;
    private String stationName;
    private String metricType;
    private BigDecimal value;
    private String unit;
    private LocalDateTime observedAt;
    private String qualityFlag;
    private String source;
    private LocalDateTime createdAt;
}
