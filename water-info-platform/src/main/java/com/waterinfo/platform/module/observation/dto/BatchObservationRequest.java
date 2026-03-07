package com.waterinfo.platform.module.observation.dto;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;

/**
 * Batch observation upload request DTO
 */
@Data
public class BatchObservationRequest {

    private String requestId;

    @NotEmpty(message = "Observations cannot be empty")
    @Size(max = 5000, message = "Batch size cannot exceed 5000")
    @Valid
    private List<ObservationItem> observations;

    @Data
    public static class ObservationItem {

        @NotNull(message = "Station ID is required")
        private String stationId;

        @NotNull(message = "Metric type is required")
        private String metricType;

        @NotNull(message = "Value is required")
        private BigDecimal value;

        private String unit;

        @NotNull(message = "Observed time is required")
        private LocalDateTime observedAt;

        private String qualityFlag;

        private String source;
    }
}
