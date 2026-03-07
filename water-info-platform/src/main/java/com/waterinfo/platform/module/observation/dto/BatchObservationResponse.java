package com.waterinfo.platform.module.observation.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * Batch observation response DTO
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class BatchObservationResponse {

    private String requestId;
    private Integer total;
    private Integer accepted;
    private Integer rejected;
    private Integer alarmsTriggered;
}
