package com.waterinfo.platform.module.sensor.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.waterinfo.platform.common.api.PageRequest;
import com.waterinfo.platform.common.exception.BusinessException;
import com.waterinfo.platform.common.exception.ErrorCode;
import com.waterinfo.platform.module.audit.service.AuditLogService;
import com.waterinfo.platform.module.sensor.dto.CreateSensorRequest;
import com.waterinfo.platform.module.sensor.dto.UpdateSensorRequest;
import com.waterinfo.platform.module.sensor.entity.Sensor;
import com.waterinfo.platform.module.sensor.mapper.SensorMapper;
import com.waterinfo.platform.module.sensor.vo.SensorVO;
import com.waterinfo.platform.module.station.entity.Station;
import com.waterinfo.platform.module.station.mapper.StationMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.time.LocalDateTime;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * Sensor service
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class SensorService extends ServiceImpl<SensorMapper, Sensor> {

    private final StationMapper stationMapper;
    private final AuditLogService auditLogService;

    /**
     * Create a new sensor
     */
    @Transactional
    public SensorVO createSensor(CreateSensorRequest request) {
        // Verify station exists
        Station station = stationMapper.selectById(request.getStationId());
        if (station == null) {
            throw new BusinessException(ErrorCode.STATION_NOT_FOUND);
        }

        Sensor sensor = Sensor.builder()
                .stationId(request.getStationId())
                .type(request.getType())
                .unit(request.getUnit())
                .samplingIntervalSec(request.getSamplingIntervalSec() != null ? request.getSamplingIntervalSec() : 300)
                .status("ACTIVE")
                .meta(request.getMeta())
                .build();

        save(sensor);

        auditLogService.logAsync("SENSOR_CREATE", "SENSOR", sensor.getId(),
                Map.of("stationId", sensor.getStationId(), "type", sensor.getType()));

        return convertToVO(sensor, station);
    }

    /**
     * Update sensor
     */
    @Transactional
    public SensorVO updateSensor(String id, UpdateSensorRequest request) {
        Sensor sensor = getById(id);
        if (sensor == null) {
            throw new BusinessException(ErrorCode.SENSOR_NOT_FOUND);
        }

        if (StringUtils.hasText(request.getType())) {
            sensor.setType(request.getType());
        }
        if (StringUtils.hasText(request.getUnit())) {
            sensor.setUnit(request.getUnit());
        }
        if (request.getSamplingIntervalSec() != null) {
            sensor.setSamplingIntervalSec(request.getSamplingIntervalSec());
        }
        if (StringUtils.hasText(request.getStatus())) {
            sensor.setStatus(request.getStatus());
        }
        if (request.getMeta() != null) {
            sensor.setMeta(request.getMeta());
        }

        updateById(sensor);

        auditLogService.logAsync("SENSOR_UPDATE", "SENSOR", sensor.getId(),
                Map.of("stationId", sensor.getStationId(), "type", sensor.getType()));

        Station station = stationMapper.selectById(sensor.getStationId());
        return convertToVO(sensor, station);
    }

    /**
     * Update sensor heartbeat
     */
    @Transactional
    public void updateHeartbeat(String id) {
        Sensor sensor = getById(id);
        if (sensor == null) {
            throw new BusinessException(ErrorCode.SENSOR_NOT_FOUND);
        }

        sensor.setLastSeenAt(LocalDateTime.now());
        updateById(sensor);
    }

    /**
     * Get sensor by ID
     */
    public SensorVO getSensorById(String id) {
        Sensor sensor = getById(id);
        if (sensor == null) {
            throw new BusinessException(ErrorCode.SENSOR_NOT_FOUND);
        }
        Station station = stationMapper.selectById(sensor.getStationId());
        return convertToVO(sensor, station);
    }

    /**
     * Query sensors with pagination
     */
    public Page<SensorVO> querySensors(PageRequest pageRequest, String stationId, String type, String status) {
        Page<Sensor> page = new Page<>(pageRequest.getPage(), pageRequest.getSize());

        LambdaQueryWrapper<Sensor> wrapper = new LambdaQueryWrapper<>();

        if (StringUtils.hasText(stationId)) {
            wrapper.eq(Sensor::getStationId, stationId);
        }
        if (StringUtils.hasText(type)) {
            wrapper.eq(Sensor::getType, type);
        }
        if (StringUtils.hasText(status)) {
            wrapper.eq(Sensor::getStatus, status);
        }

        wrapper.orderByDesc(Sensor::getCreatedAt);

        Page<Sensor> sensorPage = page(page, wrapper);

        Page<SensorVO> voPage = new Page<>(sensorPage.getCurrent(), sensorPage.getSize(), sensorPage.getTotal());
        voPage.setRecords(sensorPage.getRecords().stream()
                .map(sensor -> {
                    Station station = stationMapper.selectById(sensor.getStationId());
                    return convertToVO(sensor, station);
                })
                .collect(Collectors.toList()));

        return voPage;
    }

    /**
     * Delete sensor
     */
    @Transactional
    public void deleteSensor(String id) {
        Sensor sensor = getById(id);
        if (sensor == null) {
            throw new BusinessException(ErrorCode.SENSOR_NOT_FOUND);
        }

        removeById(id);

        auditLogService.logAsync("SENSOR_DELETE", "SENSOR", id,
                Map.of("stationId", sensor.getStationId(), "type", sensor.getType()));
    }

    /**
     * Convert entity to VO
     */
    private SensorVO convertToVO(Sensor sensor, Station station) {
        return SensorVO.builder()
                .id(sensor.getId())
                .stationId(sensor.getStationId())
                .stationCode(station != null ? station.getCode() : null)
                .stationName(station != null ? station.getName() : null)
                .type(sensor.getType())
                .unit(sensor.getUnit())
                .samplingIntervalSec(sensor.getSamplingIntervalSec())
                .status(sensor.getStatus())
                .lastSeenAt(sensor.getLastSeenAt())
                .meta(sensor.getMeta())
                .createdAt(sensor.getCreatedAt())
                .updatedAt(sensor.getUpdatedAt())
                .build();
    }
}
