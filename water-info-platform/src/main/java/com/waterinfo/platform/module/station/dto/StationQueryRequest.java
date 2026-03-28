package com.waterinfo.platform.module.station.dto;

import lombok.Data;
import lombok.EqualsAndHashCode;
import com.waterinfo.platform.common.api.PageRequest;

/**
 * Station query request DTO
 */
@Data
@EqualsAndHashCode(callSuper = true)
public class StationQueryRequest extends PageRequest {

    private String type;
    private String adminRegion;
    private String status;
    private String keyword;
}
