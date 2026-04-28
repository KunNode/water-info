package com.waterinfo.platform.module.aiassessment.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

import java.time.LocalDateTime;

@Data
public class UpsertAiAssessmentRequest {

    @NotBlank
    private String stationId;

    private String metricType;

    @NotBlank
    private String level;

    @NotBlank
    private String summary;

    private String planExcerpt;

    @NotBlank
    private String source;

    private LocalDateTime assessedAt;
}
