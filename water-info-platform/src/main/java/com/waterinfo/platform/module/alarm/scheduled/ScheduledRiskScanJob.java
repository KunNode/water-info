package com.waterinfo.platform.module.alarm.scheduled;

import com.waterinfo.platform.module.alarm.dto.AlarmCreateResult;
import com.waterinfo.platform.module.alarm.event.RiskEscalatedEvent;
import com.waterinfo.platform.module.alarm.service.AlarmService;
import com.waterinfo.platform.module.observation.dto.StationMetricKey;
import com.waterinfo.platform.module.observation.entity.Observation;
import com.waterinfo.platform.module.observation.mapper.ObservationMapper;
import com.waterinfo.platform.module.threshold.entity.ThresholdRule;
import com.waterinfo.platform.module.threshold.service.ThresholdRuleService;
import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Timer;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.Duration;
import java.time.LocalDateTime;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.function.Function;
import java.util.stream.Collectors;

@Slf4j
@Component
@RequiredArgsConstructor
public class ScheduledRiskScanJob {

    private static final Set<String> AI_TRIGGER_LEVELS = Set.of("HIGH", "CRITICAL");

    private final RiskScanProperties properties;
    private final ThresholdRuleService thresholdRuleService;
    private final ObservationMapper observationMapper;
    private final AlarmService alarmService;
    private final ApplicationEventPublisher eventPublisher;
    private final MeterRegistry meterRegistry;

    @Scheduled(fixedDelayString = "${water-info.risk-scan.lightweight.interval-ms:90000}")
    public void scan() {
        RiskScanProperties.Lightweight lightweight = properties.getLightweight();
        if (!lightweight.isEnabled()) {
            return;
        }

        long startedAt = System.nanoTime();
        Counter runs = meterRegistry.counter("risk_scan_runs_total");
        Timer.Sample sample = Timer.start(meterRegistry);
        runs.increment();

        try {
            runScan(lightweight);
        } catch (Exception ex) {
            log.warn("Scheduled risk scan failed: {}", ex.getMessage(), ex);
        } finally {
            sample.stop(meterRegistry.timer("risk_scan_duration_seconds"));
            long elapsedMs = Duration.ofNanos(System.nanoTime() - startedAt).toMillis();
            if (elapsedMs > lightweight.getIntervalMs()) {
                log.warn("Scheduled risk scan took {}ms, exceeding interval {}ms", elapsedMs, lightweight.getIntervalMs());
            }
        }
    }

    private void runScan(RiskScanProperties.Lightweight lightweight) {
        List<ThresholdRule> rules = thresholdRuleService.findEnabledRules(null, null);
        if (rules.isEmpty()) {
            return;
        }

        Map<String, List<ThresholdRule>> rulesByKey = rules.stream()
                .filter(rule -> rule.getStationId() != null && rule.getMetricType() != null)
                .collect(Collectors.groupingBy(rule -> key(rule.getStationId(), rule.getMetricType())));

        List<StationMetricKey> keys = rulesByKey.values().stream()
                .map(group -> group.get(0))
                .map(rule -> new StationMetricKey(rule.getStationId(), rule.getMetricType()))
                .toList();
        if (keys.isEmpty()) {
            return;
        }

        LocalDateTime since = LocalDateTime.now().minusSeconds(lightweight.getWindowSeconds());
        Map<String, Observation> latestByKey = observationMapper.selectLatestByStationMetricPairs(keys, since).stream()
                .collect(Collectors.toMap(
                        observation -> key(observation.getStationId(), observation.getMetricType()),
                        Function.identity(),
                        (left, right) -> left.getObservedAt().isAfter(right.getObservedAt()) ? left : right
                ));

        latestByKey.forEach((stationMetric, observation) -> {
            try {
                ThresholdRule hit = pickHighestSeverityHit(observation, rulesByKey.get(stationMetric));
                if (hit == null) {
                    return;
                }
                emitAlarm(observation, hit);
            } catch (Exception ex) {
                log.warn("Risk scan item failed: key={}, error={}", stationMetric, ex.getMessage(), ex);
            }
        });
    }

    private ThresholdRule pickHighestSeverityHit(Observation observation, List<ThresholdRule> rules) {
        if (observation == null || rules == null || rules.isEmpty() || observation.getValue() == null) {
            return null;
        }
        return rules.stream()
                .filter(rule -> rule.getThresholdValue() != null)
                .filter(rule -> observation.getValue().compareTo(rule.getThresholdValue()) >= 0)
                .max(Comparator
                        .comparingInt((ThresholdRule rule) -> severity(rule.getLevel()))
                        .thenComparing(ThresholdRule::getThresholdValue))
                .orElse(null);
    }

    private void emitAlarm(Observation observation, ThresholdRule rule) {
        String message = String.format("定时巡检发现 %s 超过 %s 阈值：当前值 %s，阈值 %s",
                observation.getMetricType(), rule.getLevel(), observation.getValue(), rule.getThresholdValue());
        AlarmCreateResult result = alarmService.createOrUpdateAlarmWithResult(
                observation.getStationId(),
                observation.getMetricType(),
                normalizeLevel(rule.getLevel()),
                Objects.requireNonNullElse(observation.getObservedAt(), LocalDateTime.now()),
                message,
                "SCHEDULED"
        );
        meterRegistry.counter("risk_scan_alarms_emitted_total", "level", normalizeLevel(rule.getLevel())).increment();

        if (result.isNewOrEscalated() && AI_TRIGGER_LEVELS.contains(normalizeLevel(rule.getLevel()))) {
            eventPublisher.publishEvent(new RiskEscalatedEvent(
                    observation.getStationId(),
                    observation.getMetricType(),
                    normalizeLevel(rule.getLevel()),
                    observation.getValue(),
                    observation.getObservedAt()
            ));
        }
    }

    private String normalizeLevel(String level) {
        if (level == null) {
            return "INFO";
        }
        return level.toUpperCase();
    }

    private int severity(String level) {
        return switch (normalizeLevel(level)) {
            case "CRITICAL" -> 5;
            case "HIGH" -> 4;
            case "WARNING", "MEDIUM" -> 3;
            case "LOW" -> 2;
            default -> 1;
        };
    }

    private String key(String stationId, String metricType) {
        return stationId + "::" + metricType;
    }
}
