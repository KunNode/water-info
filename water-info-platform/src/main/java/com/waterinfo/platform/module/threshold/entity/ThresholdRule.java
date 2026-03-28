package com.waterinfo.platform.module.threshold.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * Threshold rule entity
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@TableName("threshold_rule")
public class ThresholdRule {

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String stationId;

    private String metricType;

    private String level;

    private BigDecimal thresholdValue;

    private Integer durationMin;

    private BigDecimal rateThreshold;

    private Boolean enabled;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;
}
