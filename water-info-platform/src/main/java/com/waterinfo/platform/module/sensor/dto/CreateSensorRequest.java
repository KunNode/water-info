package com.waterinfo.platform.module.sensor.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

import java.util.Map;

/**
 * Create sensor request DTO
 */
@Data
public class CreateSensorRequest {

    @NotBlank(message = "Station ID is required")
    private String stationId;

    @NotBlank(message = "Sensor type is required")
    private String type;

    private String unit;

    private Integer samplingIntervalSec;

    private Map<String, Object> meta;
}
