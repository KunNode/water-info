package com.waterinfo.platform.module.aiassessment.vo;

import lombok.Builder;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@Builder
public class AiAssessmentVO {

    private String id;
    private String stationId;
    private String stationName;
    private String metricType;
    private String level;
    private String summary;
    private String planExcerpt;
    private String source;
    private LocalDateTime assessedAt;
    private LocalDateTime createdAt;
}
