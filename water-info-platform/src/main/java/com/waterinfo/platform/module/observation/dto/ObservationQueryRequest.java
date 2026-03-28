package com.waterinfo.platform.module.observation.dto;

import lombok.Data;
import lombok.EqualsAndHashCode;
import com.waterinfo.platform.common.api.PageRequest;

import java.time.LocalDateTime;

/**
 * Observation query request DTO
 */
@Data
@EqualsAndHashCode(callSuper = true)
public class ObservationQueryRequest extends PageRequest {

    private String stationId;
    private String metricType;
    private LocalDateTime start;
    private LocalDateTime end;
}
