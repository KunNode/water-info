package com.waterinfo.platform.module.observation.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * Observation entity (time series data)
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@TableName("observation")
public class Observation {

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String stationId;

    private String metricType;

    private BigDecimal value;

    private String unit;

    private LocalDateTime observedAt;

    private String qualityFlag;

    private String source;

    private String requestId;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;
}
