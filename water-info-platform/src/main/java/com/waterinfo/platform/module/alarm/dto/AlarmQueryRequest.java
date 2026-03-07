package com.waterinfo.platform.module.alarm.dto;

import lombok.Data;
import lombok.EqualsAndHashCode;
import com.waterinfo.platform.common.api.PageRequest;

import java.time.LocalDateTime;

/**
 * Alarm query request DTO
 */
@Data
@EqualsAndHashCode(callSuper = true)
public class AlarmQueryRequest extends PageRequest {

    private String stationId;
    private String metricType;
    private String level;
    private String status;
    private LocalDateTime start;
    private LocalDateTime end;
}
