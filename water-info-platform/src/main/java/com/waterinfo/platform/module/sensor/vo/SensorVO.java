package com.waterinfo.platform.module.sensor.vo;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.Map;

/**
 * Sensor view object
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class SensorVO {

    private String id;
    private String stationId;
    private String stationCode;
    private String stationName;
    private String type;
    private String unit;
    private Integer samplingIntervalSec;
    private String status;
    private LocalDateTime lastSeenAt;
    private Map<String, Object> meta;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
