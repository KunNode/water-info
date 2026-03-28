package com.waterinfo.platform.module.threshold.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.waterinfo.platform.common.api.PageRequest;
import com.waterinfo.platform.common.exception.BusinessException;
import com.waterinfo.platform.common.exception.ErrorCode;
import com.waterinfo.platform.module.audit.service.AuditLogService;
import com.waterinfo.platform.module.station.entity.Station;
import com.waterinfo.platform.module.station.mapper.StationMapper;
import com.waterinfo.platform.module.threshold.dto.CreateThresholdRuleRequest;
import com.waterinfo.platform.module.threshold.dto.UpdateThresholdRuleRequest;
import com.waterinfo.platform.module.threshold.entity.ThresholdRule;
import com.waterinfo.platform.module.threshold.mapper.ThresholdRuleMapper;
import com.waterinfo.platform.module.threshold.vo.ThresholdRuleVO;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.cache.annotation.CacheEvict;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * Threshold rule service
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ThresholdRuleService extends ServiceImpl<ThresholdRuleMapper, ThresholdRule> {

    private final StationMapper stationMapper;
    private final AuditLogService auditLogService;

    /**
     * Create a new threshold rule
     */
    @Transactional
    @CacheEvict(value = "thresholds", allEntries = true)
    public ThresholdRuleVO createRule(CreateThresholdRuleRequest request) {
        // Verify station exists
        Station station = stationMapper.selectById(request.getStationId());
        if (station == null) {
            throw new BusinessException(ErrorCode.STATION_NOT_FOUND);
        }

        ThresholdRule rule = ThresholdRule.builder()
                .stationId(request.getStationId())
                .metricType(request.getMetricType())
                .level(request.getLevel())
                .thresholdValue(request.getThresholdValue())
                .durationMin(request.getDurationMin())
                .rateThreshold(request.getRateThreshold())
                .enabled(true)
                .build();

        save(rule);

        auditLogService.logAsync("THRESHOLD_CREATE", "THRESHOLD_RULE", rule.getId(),
                Map.of("stationId", rule.getStationId(), "metricType", rule.getMetricType(), 
                       "level", rule.getLevel()));

        return convertToVO(rule, station);
    }

    /**
     * Update threshold rule
     */
    @Transactional
    @CacheEvict(value = "thresholds", key = "#id")
    public ThresholdRuleVO updateRule(String id, UpdateThresholdRuleRequest request) {
        ThresholdRule rule = getById(id);
        if (rule == null) {
            throw new BusinessException(ErrorCode.THRESHOLD_NOT_FOUND);
        }

        if (StringUtils.hasText(request.getLevel())) {
            rule.setLevel(request.getLevel());
        }
        if (request.getThresholdValue() != null) {
            rule.setThresholdValue(request.getThresholdValue());
        }
        if (request.getDurationMin() != null) {
            rule.setDurationMin(request.getDurationMin());
        }
        if (request.getRateThreshold() != null) {
            rule.setRateThreshold(request.getRateThreshold());
        }

        updateById(rule);

        auditLogService.logAsync("THRESHOLD_UPDATE", "THRESHOLD_RULE", rule.getId(),
                Map.of("stationId", rule.getStationId(), "metricType", rule.getMetricType()));

        Station station = stationMapper.selectById(rule.getStationId());
        return convertToVO(rule, station);
    }

    /**
     * Enable threshold rule
     */
    @Transactional
    @CacheEvict(value = "thresholds", allEntries = true)
    public void enableRule(String id) {
        ThresholdRule rule = getById(id);
        if (rule == null) {
            throw new BusinessException(ErrorCode.THRESHOLD_NOT_FOUND);
        }

        rule.setEnabled(true);
        updateById(rule);

        auditLogService.logAsync("THRESHOLD_ENABLE", "THRESHOLD_RULE", rule.getId(),
                Map.of("stationId", rule.getStationId()));
    }

    /**
     * Disable threshold rule
     */
    @Transactional
    @CacheEvict(value = "thresholds", allEntries = true)
    public void disableRule(String id) {
        ThresholdRule rule = getById(id);
        if (rule == null) {
            throw new BusinessException(ErrorCode.THRESHOLD_NOT_FOUND);
        }

        rule.setEnabled(false);
        updateById(rule);

        auditLogService.logAsync("THRESHOLD_DISABLE", "THRESHOLD_RULE", rule.getId(),
                Map.of("stationId", rule.getStationId()));
    }

    /**
     * Get threshold rule by ID
     */
    @Cacheable(value = "thresholds", key = "#id", unless = "#result == null")
    public ThresholdRuleVO getRuleById(String id) {
        ThresholdRule rule = getById(id);
        if (rule == null) {
            throw new BusinessException(ErrorCode.THRESHOLD_NOT_FOUND);
        }
        Station station = stationMapper.selectById(rule.getStationId());
        return convertToVO(rule, station);
    }

    /**
     * Query threshold rules with pagination
     */
    public Page<ThresholdRuleVO> queryRules(PageRequest pageRequest, String stationId, 
                                            String metricType, Boolean enabled) {
        Page<ThresholdRule> page = new Page<>(pageRequest.getPage(), pageRequest.getSize());

        LambdaQueryWrapper<ThresholdRule> wrapper = new LambdaQueryWrapper<>();

        if (StringUtils.hasText(stationId)) {
            wrapper.eq(ThresholdRule::getStationId, stationId);
        }
        if (StringUtils.hasText(metricType)) {
            wrapper.eq(ThresholdRule::getMetricType, metricType);
        }
        if (enabled != null) {
            wrapper.eq(ThresholdRule::getEnabled, enabled);
        }

        wrapper.orderByDesc(ThresholdRule::getCreatedAt);

        Page<ThresholdRule> rulePage = page(page, wrapper);

        Page<ThresholdRuleVO> voPage = new Page<>(rulePage.getCurrent(), rulePage.getSize(), rulePage.getTotal());
        voPage.setRecords(rulePage.getRecords().stream()
                .map(rule -> {
                    Station station = stationMapper.selectById(rule.getStationId());
                    return convertToVO(rule, station);
                })
                .collect(Collectors.toList()));

        return voPage;
    }

    /**
     * Find enabled rules by station and metric type
     */
    public List<ThresholdRule> findEnabledRules(String stationId, String metricType) {
        return list(new LambdaQueryWrapper<ThresholdRule>()
                .eq(ThresholdRule::getStationId, stationId)
                .eq(ThresholdRule::getMetricType, metricType)
                .eq(ThresholdRule::getEnabled, true));
    }

    /**
     * Delete threshold rule
     */
    @Transactional
    @CacheEvict(value = "thresholds", allEntries = true)
    public void deleteRule(String id) {
        ThresholdRule rule = getById(id);
        if (rule == null) {
            throw new BusinessException(ErrorCode.THRESHOLD_NOT_FOUND);
        }

        removeById(id);

        auditLogService.logAsync("THRESHOLD_DELETE", "THRESHOLD_RULE", id,
                Map.of("stationId", rule.getStationId(), "metricType", rule.getMetricType()));
    }

    /**
     * Convert entity to VO
     */
    private ThresholdRuleVO convertToVO(ThresholdRule rule, Station station) {
        return ThresholdRuleVO.builder()
                .id(rule.getId())
                .stationId(rule.getStationId())
                .stationCode(station != null ? station.getCode() : null)
                .stationName(station != null ? station.getName() : null)
                .metricType(rule.getMetricType())
                .level(rule.getLevel())
                .thresholdValue(rule.getThresholdValue())
                .durationMin(rule.getDurationMin())
                .rateThreshold(rule.getRateThreshold())
                .enabled(rule.getEnabled())
                .createdAt(rule.getCreatedAt())
                .updatedAt(rule.getUpdatedAt())
                .build();
    }
}
