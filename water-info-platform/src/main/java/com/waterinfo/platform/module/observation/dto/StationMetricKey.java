package com.waterinfo.platform.module.observation.dto;

import lombok.AllArgsConstructor;
import lombok.Data;

@Data
@AllArgsConstructor
public class StationMetricKey {

    private String stationId;

    private String metricType;
}
