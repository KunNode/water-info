package com.waterinfo.platform.module.station.dto;

import lombok.Data;

import java.math.BigDecimal;

/**
 * Update station request DTO
 */
@Data
public class UpdateStationRequest {

    private String name;
    private String type;
    private String riverBasin;
    private String adminRegion;
    private BigDecimal lat;
    private BigDecimal lon;
    private BigDecimal elevation;
    private String status;
}
