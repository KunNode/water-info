package com.waterinfo.platform.module.observation.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.waterinfo.platform.common.exception.BusinessException;
import com.waterinfo.platform.common.exception.ErrorCode;
import com.waterinfo.platform.module.alarm.service.AlarmService;
import com.waterinfo.platform.module.observation.dto.BatchObservationRequest;
import com.waterinfo.platform.module.observation.dto.BatchObservationResponse;
import com.waterinfo.platform.module.observation.dto.ObservationQueryRequest;
import com.waterinfo.platform.module.observation.entity.Observation;
import com.waterinfo.platform.module.observation.mapper.ObservationMapper;
import com.waterinfo.platform.module.observation.vo.ObservationVO;
import com.waterinfo.platform.module.station.entity.Station;
import com.waterinfo.platform.module.station.mapper.StationMapper;
import com.waterinfo.platform.module.threshold.entity.ThresholdRule;
import com.waterinfo.platform.module.threshold.service.ThresholdRuleService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.*;
import java.util.stream.Collectors;

/**
 * Observation service with threshold evaluation and batch insert
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ObservationService extends ServiceImpl<ObservationMapper, Observation> {

    private final ObservationMapper observationMapper;
    private final StationMapper stationMapper;
    private final ThresholdRuleService thresholdRuleService;
    private final AlarmService alarmService;

    private static final int BATCH_SIZE = 500;

    /**
     * Batch upload observations with threshold evaluation
     */
    @Transactional
    public BatchObservationResponse batchUpload(BatchObservationRequest request) {
        List<BatchObservationRequest.ObservationItem> items = request.getObservations();
        
        if (items.size() > 5000) {
            throw new BusinessException(ErrorCode.OBSERVATION_BATCH_TOO_LARGE,
                    "Batch size exceeds limit of 5000");
        }

        String requestId = StringUtils.hasText(request.getRequestId()) 
                ? request.getRequestId() 
                : UUID.randomUUID().toString();

        int accepted = 0;
        int rejected = 0;
        int alarmsTriggered = 0;

        // Group observations by station+metric for threshold evaluation
        Map<String, List<Observation>> groupedObservations = new HashMap<>();

        List<Observation> validObservations = new ArrayList<>();

        for (BatchObservationRequest.ObservationItem item : items) {
            try {
                // Validate station exists
                Station station = stationMapper.selectById(item.getStationId());
                if (station == null) {
                    log.warn("Invalid station ID: {}", item.getStationId());
                    rejected++;
                    continue;
                }

                Observation observation = Observation.builder()
                        .id(UUID.randomUUID().toString())
                        .stationId(item.getStationId())
                        .metricType(item.getMetricType())
                        .value(item.getValue())
                        .unit(item.getUnit())
                        .observedAt(item.getObservedAt())
                        .qualityFlag(StringUtils.hasText(item.getQualityFlag()) ? item.getQualityFlag() : "GOOD")
                        .source(item.getSource())
                        .requestId(requestId)
                        .createdAt(LocalDateTime.now())
                        .build();

                validObservations.add(observation);

                // Group for threshold evaluation
                String key = item.getStationId() + ":" + item.getMetricType();
                groupedObservations.computeIfAbsent(key, k -> new ArrayList<>()).add(observation);

                accepted++;
            } catch (Exception e) {
                log.error("Error processing observation: {}", e.getMessage());
                rejected++;
            }
        }

        // Batch insert valid observations
        if (!validObservations.isEmpty()) {
            saveBatchInChunks(validObservations);
        }

        // Threshold evaluation for each station+metric group
        for (Map.Entry<String, List<Observation>> entry : groupedObservations.entrySet()) {
            String[] parts = entry.getKey().split(":");
            String stationId = parts[0];
            String metricType = parts[1];

            // Get the latest observation in this batch for evaluation
            Observation latestObs = entry.getValue().stream()
                    .max(Comparator.comparing(Observation::getObservedAt))
                    .orElse(null);

            if (latestObs != null) {
                int alarms = evaluateThresholds(stationId, metricType, latestObs.getValue(), latestObs.getObservedAt());
                alarmsTriggered += alarms;
            }
        }

        log.info("Batch upload completed: requestId={}, total={}, accepted={}, rejected={}, alarms={}",
                requestId, items.size(), accepted, rejected, alarmsTriggered);

        return BatchObservationResponse.builder()
                .requestId(requestId)
                .total(items.size())
                .accepted(accepted)
                .rejected(rejected)
                .alarmsTriggered(alarmsTriggered)
                .build();
    }

    /**
     * Save observations in batches
     */
    private void saveBatchInChunks(List<Observation> observations) {
        int total = observations.size();
        for (int i = 0; i < total; i += BATCH_SIZE) {
            int end = Math.min(i + BATCH_SIZE, total);
            List<Observation> batch = observations.subList(i, end);
            observationMapper.batchInsert(batch);
            log.debug("Inserted batch of {} observations ({}/{})", batch.size(), end, total);
        }
    }

    /**
     * Evaluate thresholds and create/update alarms
     * Returns the number of alarms triggered
     */
    private int evaluateThresholds(String stationId, String metricType, BigDecimal value, LocalDateTime observedAt) {
        List<ThresholdRule> rules = thresholdRuleService.findEnabledRules(stationId, metricType);
        
        int alarmsTriggered = 0;

        for (ThresholdRule rule : rules) {
            // Check if value exceeds threshold
            if (value.compareTo(rule.getThresholdValue()) >= 0) {
                String message = String.format("Value %.2f exceeds threshold %.2f (Level: %s)",
                        value, rule.getThresholdValue(), rule.getLevel());
                
                alarmService.createOrUpdateAlarm(stationId, metricType, rule.getLevel(), observedAt, message);
                alarmsTriggered++;
                
                log.info("Threshold exceeded: station={}, metric={}, value={}, threshold={}, level={}",
                        stationId, metricType, value, rule.getThresholdValue(), rule.getLevel());
            }
        }

        return alarmsTriggered;
    }

    /**
     * Query observations with pagination
     */
    public Page<ObservationVO> queryObservations(ObservationQueryRequest request) {
        Page<Observation> page = new Page<>(request.getPage(), request.getSize());

        LambdaQueryWrapper<Observation> wrapper = new LambdaQueryWrapper<>();

        if (StringUtils.hasText(request.getStationId())) {
            wrapper.eq(Observation::getStationId, request.getStationId());
        }
        if (StringUtils.hasText(request.getMetricType())) {
            wrapper.eq(Observation::getMetricType, request.getMetricType());
        }
        if (request.getStart() != null) {
            wrapper.ge(Observation::getObservedAt, request.getStart());
        }
        if (request.getEnd() != null) {
            wrapper.le(Observation::getObservedAt, request.getEnd());
        }

        wrapper.orderByDesc(Observation::getObservedAt);

        Page<Observation> obsPage = page(page, wrapper);

        // Batch fetch station info
        Set<String> stationIds = obsPage.getRecords().stream()
                .map(Observation::getStationId)
                .collect(Collectors.toSet());
        
        Map<String, Station> stationMap = new HashMap<>();
        if (!stationIds.isEmpty()) {
            List<Station> stations = stationMapper.selectBatchIds(stationIds);
            stationMap = stations.stream().collect(Collectors.toMap(Station::getId, s -> s));
        }

        Map<String, Station> finalStationMap = stationMap;
        Page<ObservationVO> voPage = new Page<>(obsPage.getCurrent(), obsPage.getSize(), obsPage.getTotal());
        voPage.setRecords(obsPage.getRecords().stream()
                .map(obs -> convertToVO(obs, finalStationMap.get(obs.getStationId())))
                .collect(Collectors.toList()));

        return voPage;
    }

    /**
     * Get latest observation for station and metric type
     */
    public ObservationVO getLatestObservation(String stationId, String metricType) {
        LambdaQueryWrapper<Observation> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(Observation::getStationId, stationId);
        
        if (StringUtils.hasText(metricType)) {
            wrapper.eq(Observation::getMetricType, metricType);
        }
        
        wrapper.orderByDesc(Observation::getObservedAt);
        wrapper.last("LIMIT 1");

        Observation obs = getOne(wrapper);
        if (obs == null) {
            return null;
        }

        Station station = stationMapper.selectById(obs.getStationId());
        return convertToVO(obs, station);
    }

    /**
     * Convert entity to VO
     */
    private ObservationVO convertToVO(Observation obs, Station station) {
        return ObservationVO.builder()
                .id(obs.getId())
                .stationId(obs.getStationId())
                .stationCode(station != null ? station.getCode() : null)
                .stationName(station != null ? station.getName() : null)
                .metricType(obs.getMetricType())
                .value(obs.getValue())
                .unit(obs.getUnit())
                .observedAt(obs.getObservedAt())
                .qualityFlag(obs.getQualityFlag())
                .source(obs.getSource())
                .createdAt(obs.getCreatedAt())
                .build();
    }
}
