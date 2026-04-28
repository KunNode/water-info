package com.waterinfo.platform.module.alarm.event;

import java.math.BigDecimal;
import java.time.LocalDateTime;

public record RiskEscalatedEvent(
        String stationId,
        String metricType,
        String level,
        BigDecimal value,
        LocalDateTime observedAt
) {
}
