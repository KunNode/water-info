package com.waterinfo.platform.module.station.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Data;

import java.math.BigDecimal;

/**
 * Create station request DTO
 */
@Data
public class CreateStationRequest {

    @NotBlank(message = "Station code is required")
    @Size(max = 64, message = "Station code must not exceed 64 characters")
    private String code;

    @NotBlank(message = "Station name is required")
    @Size(max = 128, message = "Station name must not exceed 128 characters")
    private String name;

    @NotBlank(message = "Station type is required")
    private String type;

    @Size(max = 128, message = "River basin must not exceed 128 characters")
    private String riverBasin;

    @Size(max = 128, message = "Admin region must not exceed 128 characters")
    private String adminRegion;

    private BigDecimal lat;

    private BigDecimal lon;

    private BigDecimal elevation;
}
