package com.waterinfo.platform.module.alarm.vo;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

/**
 * Alarm view object
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class AlarmVO {

    private String id;
    private String stationId;
    private String stationCode;
    private String stationName;
    private String metricType;
    private String level;
    private LocalDateTime startAt;
    private LocalDateTime lastTriggerAt;
    private LocalDateTime endAt;
    private String status;
    private String message;
    private String acknowledgedBy;
    private String acknowledgedByName;
    private LocalDateTime acknowledgedAt;
    private String closedBy;
    private String closedByName;
    private LocalDateTime closedAt;
    private LocalDateTime createdAt;
}
