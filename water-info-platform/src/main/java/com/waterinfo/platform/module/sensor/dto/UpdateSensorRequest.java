package com.waterinfo.platform.module.sensor.dto;

import lombok.Data;

import java.util.Map;

/**
 * Update sensor request DTO
 */
@Data
public class UpdateSensorRequest {

    private String type;
    private String unit;
    private Integer samplingIntervalSec;
    private String status;
    private Map<String, Object> meta;
}
