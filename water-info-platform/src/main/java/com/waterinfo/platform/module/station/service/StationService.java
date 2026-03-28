package com.waterinfo.platform.module.station.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.waterinfo.platform.common.exception.BusinessException;
import com.waterinfo.platform.common.exception.ErrorCode;
import com.waterinfo.platform.module.audit.service.AuditLogService;
import com.waterinfo.platform.module.station.dto.CreateStationRequest;
import com.waterinfo.platform.module.station.dto.StationQueryRequest;
import com.waterinfo.platform.module.station.dto.UpdateStationRequest;
import com.waterinfo.platform.module.station.entity.Station;
import com.waterinfo.platform.module.station.mapper.StationMapper;
import com.waterinfo.platform.module.station.vo.StationVO;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.cache.annotation.CacheEvict;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

/**
 * Station service
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class StationService extends ServiceImpl<StationMapper, Station> {

    private final AuditLogService auditLogService;

    private static final String TYPE_RAIN_GAUGE = "RAIN_GAUGE";
    private static final Set<String> SUPPORTED_STATION_TYPES = Set.of(
            TYPE_RAIN_GAUGE, "WATER_LEVEL", "FLOW", "RESERVOIR", "GATE", "PUMP_STATION", "OTHER"
    );
    private static final Map<String, String> STATION_TYPE_ALIASES = Map.of(
            "RAINFALL", TYPE_RAIN_GAUGE
    );

    /**
     * Create a new station
     */
    @Transactional
    @CacheEvict(value = "stations", allEntries = true)
    public StationVO createStation(CreateStationRequest request) {
        // Check if code exists
        if (existsByCode(request.getCode())) {
            throw new BusinessException(ErrorCode.STATION_CODE_EXISTS);
        }

        Station station = Station.builder()
                .code(request.getCode())
                .name(request.getName())
                .type(normalizeAndValidateStationType(request.getType()))
                .riverBasin(request.getRiverBasin())
                .adminRegion(request.getAdminRegion())
                .lat(request.getLat())
                .lon(request.getLon())
                .elevation(request.getElevation())
                .status("ACTIVE")
                .build();

        save(station);

        auditLogService.logAsync("STATION_CREATE", "STATION", station.getId(),
                Map.of("code", station.getCode(), "name", station.getName()));

        return convertToVO(station);
    }

    /**
     * Update station
     */
    @Transactional
    @CacheEvict(value = "stations", key = "#id")
    public StationVO updateStation(String id, UpdateStationRequest request) {
        Station station = getById(id);
        if (station == null) {
            throw new BusinessException(ErrorCode.STATION_NOT_FOUND);
        }

        if (StringUtils.hasText(request.getName())) {
            station.setName(request.getName());
        }
        if (StringUtils.hasText(request.getType())) {
            station.setType(normalizeAndValidateStationType(request.getType()));
        }
        if (StringUtils.hasText(request.getRiverBasin())) {
            station.setRiverBasin(request.getRiverBasin());
        }
        if (StringUtils.hasText(request.getAdminRegion())) {
            station.setAdminRegion(request.getAdminRegion());
        }
        if (request.getLat() != null) {
            station.setLat(request.getLat());
        }
        if (request.getLon() != null) {
            station.setLon(request.getLon());
        }
        if (request.getElevation() != null) {
            station.setElevation(request.getElevation());
        }
        if (StringUtils.hasText(request.getStatus())) {
            station.setStatus(request.getStatus());
        }

        updateById(station);

        auditLogService.logAsync("STATION_UPDATE", "STATION", station.getId(),
                Map.of("code", station.getCode(), "name", station.getName()));

        return convertToVO(station);
    }

    /**
     * Get station by ID
     */
    @Cacheable(value = "stations", key = "#id", unless = "#result == null")
    public StationVO getStationById(String id) {
        Station station = getById(id);
        if (station == null) {
            throw new BusinessException(ErrorCode.STATION_NOT_FOUND);
        }
        return convertToVO(station);
    }

    /**
     * Query stations with pagination
     */
    public Page<StationVO> queryStations(StationQueryRequest request) {
        Page<Station> page = new Page<>(request.getPage(), request.getSize());

        LambdaQueryWrapper<Station> wrapper = new LambdaQueryWrapper<>();

        if (StringUtils.hasText(request.getType())) {
            wrapper.eq(Station::getType, normalizeAndValidateStationType(request.getType()));
        }
        if (StringUtils.hasText(request.getAdminRegion())) {
            wrapper.eq(Station::getAdminRegion, request.getAdminRegion());
        }
        if (StringUtils.hasText(request.getStatus())) {
            wrapper.eq(Station::getStatus, request.getStatus());
        }
        if (StringUtils.hasText(request.getKeyword())) {
            wrapper.and(w -> w
                    .like(Station::getCode, request.getKeyword())
                    .or()
                    .like(Station::getName, request.getKeyword()));
        }

        wrapper.orderByDesc(Station::getCreatedAt);

        Page<Station> stationPage = page(page, wrapper);

        Page<StationVO> voPage = new Page<>(stationPage.getCurrent(), stationPage.getSize(), stationPage.getTotal());
        voPage.setRecords(stationPage.getRecords().stream()
                .map(this::convertToVO)
                .collect(Collectors.toList()));

        return voPage;
    }

    /**
     * Delete station
     */
    @Transactional
    @CacheEvict(value = "stations", allEntries = true)
    public void deleteStation(String id) {
        Station station = getById(id);
        if (station == null) {
            throw new BusinessException(ErrorCode.STATION_NOT_FOUND);
        }

        removeById(id);

        auditLogService.logAsync("STATION_DELETE", "STATION", id,
                Map.of("code", station.getCode(), "name", station.getName()));
    }

    /**
     * Check if station code exists
     */
    public boolean existsByCode(String code) {
        return count(new LambdaQueryWrapper<Station>().eq(Station::getCode, code)) > 0;
    }

    private String normalizeAndValidateStationType(String rawType) {
        if (!StringUtils.hasText(rawType)) {
            throw new BusinessException(ErrorCode.PARAM_INVALID, "Station type is required");
        }
        String normalized = rawType.trim().toUpperCase(Locale.ROOT);
        normalized = STATION_TYPE_ALIASES.getOrDefault(normalized, normalized);
        if (!SUPPORTED_STATION_TYPES.contains(normalized)) {
            throw new BusinessException(
                    ErrorCode.PARAM_INVALID,
                    "Invalid station type: " + rawType + ". Supported values: " + SUPPORTED_STATION_TYPES
            );
        }
        return normalized;
    }

    /**
     * Convert entity to VO
     */
    private StationVO convertToVO(Station station) {
        return StationVO.builder()
                .id(station.getId())
                .code(station.getCode())
                .name(station.getName())
                .type(station.getType())
                .riverBasin(station.getRiverBasin())
                .adminRegion(station.getAdminRegion())
                .lat(station.getLat())
                .lon(station.getLon())
                .elevation(station.getElevation())
                .status(station.getStatus())
                .createdAt(station.getCreatedAt())
                .updatedAt(station.getUpdatedAt())
                .build();
    }
}
