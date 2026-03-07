package com.waterinfo.platform.module.station.vo;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * Station view object
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class StationVO {

    private String id;
    private String code;
    private String name;
    private String type;
    private String riverBasin;
    private String adminRegion;
    private BigDecimal lat;
    private BigDecimal lon;
    private BigDecimal elevation;
    private String status;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
