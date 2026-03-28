package com.waterinfo.platform.module.alarm.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

/**
 * Alarm entity
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@TableName("alarm")
public class Alarm {

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String stationId;

    private String metricType;

    private String level;

    private LocalDateTime startAt;

    private LocalDateTime lastTriggerAt;

    private LocalDateTime endAt;

    private String status;

    private String message;

    private String acknowledgedBy;

    private LocalDateTime acknowledgedAt;

    private String closedBy;

    private LocalDateTime closedAt;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;
}
