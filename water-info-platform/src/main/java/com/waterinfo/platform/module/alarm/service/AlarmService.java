package com.waterinfo.platform.module.alarm.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.waterinfo.platform.common.exception.BusinessException;
import com.waterinfo.platform.common.exception.ErrorCode;
import com.waterinfo.platform.config.AlarmWebSocketHandler;
import com.waterinfo.platform.module.alarm.dto.AlarmCreateResult;
import com.waterinfo.platform.module.alarm.dto.AlarmQueryRequest;
import com.waterinfo.platform.module.alarm.entity.Alarm;
import com.waterinfo.platform.module.alarm.mapper.AlarmMapper;
import com.waterinfo.platform.module.alarm.vo.AlarmVO;
import com.waterinfo.platform.module.audit.service.AuditLogService;
import com.waterinfo.platform.module.station.entity.Station;
import com.waterinfo.platform.module.station.mapper.StationMapper;
import com.waterinfo.platform.module.user.entity.SysUser;
import com.waterinfo.platform.module.user.mapper.SysUserMapper;
import com.waterinfo.platform.security.SecurityUser;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * Alarm service with state machine validation
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AlarmService extends ServiceImpl<AlarmMapper, Alarm> {

    private final StationMapper stationMapper;
    private final SysUserMapper userMapper;
    private final AuditLogService auditLogService;
    private final AlarmWebSocketHandler alarmWebSocketHandler;

    // Alarm status constants
    public static final String STATUS_OPEN = "OPEN";
    public static final String STATUS_ACK = "ACK";
    public static final String STATUS_CLOSED = "CLOSED";

    /**
     * Create or update alarm (called by threshold evaluation)
     */
    @Transactional
    public Alarm createOrUpdateAlarm(String stationId, String metricType, String level,
                                     LocalDateTime observedAt, String message) {
        return createOrUpdateAlarmWithResult(stationId, metricType, level, observedAt, message, "MANUAL").getAlarm();
    }

    /**
     * Create or update alarm with creation semantics for scheduled scanners.
     */
    @Transactional
    public AlarmCreateResult createOrUpdateAlarmWithResult(String stationId, String metricType, String level,
                                                           LocalDateTime observedAt, String message,
                                                           String sourceTag) {
        // Find existing OPEN alarm for same station + metric + level
        Alarm existingAlarm = getOne(new LambdaQueryWrapper<Alarm>()
                .eq(Alarm::getStationId, stationId)
                .eq(Alarm::getMetricType, metricType)
                .eq(Alarm::getLevel, level)
                .eq(Alarm::getStatus, STATUS_OPEN));

        Station station = stationMapper.selectById(stationId);

        if (existingAlarm != null) {
            // Update existing alarm
            existingAlarm.setLastTriggerAt(observedAt);
            existingAlarm.setMessage(message);
            if (StringUtils.hasText(sourceTag)) {
                existingAlarm.setSourceTag(sourceTag);
            }
            updateById(existingAlarm);
            log.info("Updated existing alarm: id={}, station={}, metric={}, level={}",
                    existingAlarm.getId(), stationId, metricType, level);

            // Broadcast update via WebSocket
            broadcastAlarmUpdate(existingAlarm, station);
            return AlarmCreateResult.builder()
                    .alarm(existingAlarm)
                    .created(false)
                    .updated(true)
                    .build();
        } else {
            // Create new alarm
            Alarm alarm = Alarm.builder()
                    .stationId(stationId)
                    .metricType(metricType)
                    .level(level)
                    .startAt(observedAt)
                    .lastTriggerAt(observedAt)
                    .status(STATUS_OPEN)
                    .message(message)
                    .sourceTag(StringUtils.hasText(sourceTag) ? sourceTag : "MANUAL")
                    .build();
            save(alarm);
            log.info("Created new alarm: id={}, station={}, metric={}, level={}",
                    alarm.getId(), stationId, metricType, level);

            // Broadcast new alarm via WebSocket
            broadcastNewAlarm(alarm, station);
            return AlarmCreateResult.builder()
                    .alarm(alarm)
                    .created(true)
                    .updated(false)
                    .build();
        }
    }

    /**
     * Broadcast new alarm via WebSocket
     */
    private void broadcastNewAlarm(Alarm alarm, Station station) {
        try {
            Map<String, Object> alarmData = new HashMap<>();
            alarmData.put("id", alarm.getId());
            alarmData.put("stationId", alarm.getStationId());
            alarmData.put("stationCode", station != null ? station.getCode() : null);
            alarmData.put("stationName", station != null ? station.getName() : null);
            alarmData.put("metricType", alarm.getMetricType());
            alarmData.put("level", alarm.getLevel());
            alarmData.put("status", alarm.getStatus());
            alarmData.put("message", alarm.getMessage());
            alarmData.put("sourceTag", alarm.getSourceTag());
            alarmData.put("startAt", alarm.getStartAt() != null ? alarm.getStartAt().toString() : null);

            alarmWebSocketHandler.broadcastAlarm(alarmData);
            log.debug("Broadcasted new alarm: id={}", alarm.getId());
        } catch (Exception e) {
            log.warn("Failed to broadcast new alarm: {}", e.getMessage());
        }
    }

    /**
     * Broadcast alarm update via WebSocket
     */
    private void broadcastAlarmUpdate(Alarm alarm, Station station) {
        try {
            Map<String, Object> alarmData = new HashMap<>();
            alarmData.put("id", alarm.getId());
            alarmData.put("stationId", alarm.getStationId());
            alarmData.put("stationCode", station != null ? station.getCode() : null);
            alarmData.put("stationName", station != null ? station.getName() : null);
            alarmData.put("metricType", alarm.getMetricType());
            alarmData.put("level", alarm.getLevel());
            alarmData.put("status", alarm.getStatus());
            alarmData.put("message", alarm.getMessage());
            alarmData.put("sourceTag", alarm.getSourceTag());
            alarmData.put("lastTriggerAt", alarm.getLastTriggerAt() != null ? alarm.getLastTriggerAt().toString() : null);

            alarmWebSocketHandler.broadcastAlarmUpdate(alarmData);
            log.debug("Broadcasted alarm update: id={}", alarm.getId());
        } catch (Exception e) {
            log.warn("Failed to broadcast alarm update: {}", e.getMessage());
        }
    }

    /**
     * Acknowledge alarm
     * Valid transition: OPEN -> ACK
     */
    @Transactional
    public AlarmVO acknowledgeAlarm(String id) {
        Alarm alarm = getById(id);
        if (alarm == null) {
            throw new BusinessException(ErrorCode.ALARM_NOT_FOUND);
        }

        // Validate state transition
        if (!STATUS_OPEN.equals(alarm.getStatus())) {
            throw new BusinessException(ErrorCode.ALARM_INVALID_STATE_TRANSITION,
                    String.format("Cannot acknowledge alarm in '%s' status. Only OPEN alarms can be acknowledged.",
                            alarm.getStatus()));
        }

        SecurityUser currentUser = getCurrentUser();

        alarm.setStatus(STATUS_ACK);
        alarm.setAcknowledgedBy(currentUser.getId());
        alarm.setAcknowledgedAt(LocalDateTime.now());
        updateById(alarm);

        auditLogService.logAsync("ALARM_ACK", "ALARM", alarm.getId(),
                Map.of("stationId", alarm.getStationId(), "metricType", alarm.getMetricType(),
                        "level", alarm.getLevel()));

        Station station = stationMapper.selectById(alarm.getStationId());

        // Broadcast alarm update via WebSocket
        broadcastAlarmUpdate(alarm, station);

        return convertToVO(alarm, station);
    }

    /**
     * Close alarm
     * Valid transitions: OPEN -> CLOSED, ACK -> CLOSED
     */
    @Transactional
    public AlarmVO closeAlarm(String id) {
        Alarm alarm = getById(id);
        if (alarm == null) {
            throw new BusinessException(ErrorCode.ALARM_NOT_FOUND);
        }

        // Validate state transition
        if (STATUS_CLOSED.equals(alarm.getStatus())) {
            throw new BusinessException(ErrorCode.ALARM_ALREADY_CLOSED);
        }

        // Allow OPEN -> CLOSED and ACK -> CLOSED
        if (!STATUS_OPEN.equals(alarm.getStatus()) && !STATUS_ACK.equals(alarm.getStatus())) {
            throw new BusinessException(ErrorCode.ALARM_INVALID_STATE_TRANSITION,
                    String.format("Cannot close alarm in '%s' status.", alarm.getStatus()));
        }

        SecurityUser currentUser = getCurrentUser();

        alarm.setStatus(STATUS_CLOSED);
        alarm.setClosedBy(currentUser.getId());
        alarm.setClosedAt(LocalDateTime.now());
        alarm.setEndAt(LocalDateTime.now());
        updateById(alarm);

        auditLogService.logAsync("ALARM_CLOSE", "ALARM", alarm.getId(),
                Map.of("stationId", alarm.getStationId(), "metricType", alarm.getMetricType(),
                        "level", alarm.getLevel(), "previousStatus",
                        STATUS_ACK.equals(alarm.getStatus()) ? STATUS_ACK : STATUS_OPEN));

        Station station = stationMapper.selectById(alarm.getStationId());

        // Broadcast alarm update via WebSocket (status changed to CLOSED)
        broadcastAlarmUpdate(alarm, station);

        return convertToVO(alarm, station);
    }

    /**
     * Get alarm by ID
     */
    public AlarmVO getAlarmById(String id) {
        Alarm alarm = getById(id);
        if (alarm == null) {
            throw new BusinessException(ErrorCode.ALARM_NOT_FOUND);
        }
        Station station = stationMapper.selectById(alarm.getStationId());
        return convertToVO(alarm, station);
    }

    /**
     * Query alarms with pagination
     */
    public Page<AlarmVO> queryAlarms(AlarmQueryRequest request) {
        Page<Alarm> page = new Page<>(request.getPage(), request.getSize());

        LambdaQueryWrapper<Alarm> wrapper = new LambdaQueryWrapper<>();

        if (StringUtils.hasText(request.getStationId())) {
            wrapper.eq(Alarm::getStationId, request.getStationId());
        }
        if (StringUtils.hasText(request.getMetricType())) {
            wrapper.eq(Alarm::getMetricType, request.getMetricType());
        }
        if (StringUtils.hasText(request.getLevel())) {
            wrapper.eq(Alarm::getLevel, request.getLevel());
        }
        if (StringUtils.hasText(request.getStatus())) {
            wrapper.eq(Alarm::getStatus, request.getStatus());
        }
        if (request.getStart() != null) {
            wrapper.ge(Alarm::getLastTriggerAt, request.getStart());
        }
        if (request.getEnd() != null) {
            wrapper.le(Alarm::getLastTriggerAt, request.getEnd());
        }

        wrapper.orderByDesc(Alarm::getLastTriggerAt);

        Page<Alarm> alarmPage = page(page, wrapper);

        Page<AlarmVO> voPage = new Page<>(alarmPage.getCurrent(), alarmPage.getSize(), alarmPage.getTotal());
        voPage.setRecords(alarmPage.getRecords().stream()
                .map(alarm -> {
                    Station station = stationMapper.selectById(alarm.getStationId());
                    return convertToVO(alarm, station);
                })
                .collect(Collectors.toList()));

        return voPage;
    }

    /**
     * Get current security user
     */
    private SecurityUser getCurrentUser() {
        return (SecurityUser) SecurityContextHolder.getContext().getAuthentication().getPrincipal();
    }

    /**
     * Get username by user ID
     */
    private String getUsernameById(String userId) {
        if (!StringUtils.hasText(userId)) {
            return null;
        }
        SysUser user = userMapper.selectById(userId);
        return user != null ? user.getRealName() : null;
    }

    /**
     * Convert entity to VO
     */
    private AlarmVO convertToVO(Alarm alarm, Station station) {
        return AlarmVO.builder()
                .id(alarm.getId())
                .stationId(alarm.getStationId())
                .stationCode(station != null ? station.getCode() : null)
                .stationName(station != null ? station.getName() : null)
                .metricType(alarm.getMetricType())
                .level(alarm.getLevel())
                .startAt(alarm.getStartAt())
                .lastTriggerAt(alarm.getLastTriggerAt())
                .endAt(alarm.getEndAt())
                .status(alarm.getStatus())
                .message(alarm.getMessage())
                .sourceTag(alarm.getSourceTag())
                .acknowledgedBy(alarm.getAcknowledgedBy())
                .acknowledgedByName(getUsernameById(alarm.getAcknowledgedBy()))
                .acknowledgedAt(alarm.getAcknowledgedAt())
                .closedBy(alarm.getClosedBy())
                .closedByName(getUsernameById(alarm.getClosedBy()))
                .closedAt(alarm.getClosedAt())
                .createdAt(alarm.getCreatedAt())
                .build();
    }
}
