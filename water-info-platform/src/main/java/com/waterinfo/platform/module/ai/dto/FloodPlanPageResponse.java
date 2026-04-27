package com.waterinfo.platform.module.ai.dto;

import lombok.Data;

import java.util.List;

/**
 * Paginated flood emergency plan response DTO.
 */
@Data
public class FloodPlanPageResponse {

    private List<FloodPlanResponse> records;
    private long total;
    private int page;
    private int size;
    private long pages;
}
