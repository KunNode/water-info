package com.waterinfo.platform.module.observation.service;

import com.waterinfo.platform.module.alarm.service.AlarmService;
import com.waterinfo.platform.module.observation.dto.LatestObservationBatchRequest;
import com.waterinfo.platform.module.observation.entity.Observation;
import com.waterinfo.platform.module.observation.mapper.ObservationMapper;
import com.waterinfo.platform.module.observation.vo.ObservationVO;
import com.waterinfo.platform.module.station.entity.Station;
import com.waterinfo.platform.module.station.mapper.StationMapper;
import com.waterinfo.platform.module.threshold.service.ThresholdRuleService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.groups.Tuple.tuple;
import static org.mockito.ArgumentMatchers.anyCollection;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class ObservationServiceTest {

    @Mock
    private ObservationMapper observationMapper;

    @Mock
    private StationMapper stationMapper;

    @Mock
    private ThresholdRuleService thresholdRuleService;

    @Mock
    private AlarmService alarmService;

    private ObservationService observationService;

    @BeforeEach
    void setUp() {
        observationService = new ObservationService(observationMapper, stationMapper, thresholdRuleService, alarmService);
    }

    @Test
    void getLatestObservationsReturnsLatestValuesInRequestOrder() {
        LocalDateTime now = LocalDateTime.of(2026, 4, 15, 16, 0);
        LatestObservationBatchRequest.Item flowRequest = LatestObservationBatchRequest.Item.builder()
                .stationId("station-flow")
                .metricType("FLOW")
                .build();
        LatestObservationBatchRequest.Item waterLevelRequest = LatestObservationBatchRequest.Item.builder()
                .stationId("station-water")
                .metricType("WATER_LEVEL")
                .build();

        Observation latestWaterLevel = Observation.builder()
                .id("obs-water")
                .stationId("station-water")
                .metricType("WATER_LEVEL")
                .value(new BigDecimal("4.35"))
                .unit("m")
                .observedAt(now.minusMinutes(5))
                .qualityFlag("GOOD")
                .source("sensor-water")
                .createdAt(now.minusMinutes(4))
                .build();
        Observation latestFlow = Observation.builder()
                .id("obs-flow")
                .stationId("station-flow")
                .metricType("FLOW")
                .value(new BigDecimal("520.0"))
                .unit("m3/s")
                .observedAt(now.minusMinutes(3))
                .qualityFlag("GOOD")
                .source("sensor-flow")
                .createdAt(now.minusMinutes(2))
                .build();

        Station waterStation = Station.builder()
                .id("station-water")
                .code("ST_WL_CP_01")
                .name("翠屏湖心水位站")
                .build();
        Station flowStation = Station.builder()
                .id("station-flow")
                .code("ST_FLOW_CP_01")
                .name("翠屏出湖流量站")
                .build();

        when(observationMapper.selectLatestByStationMetricPairs(List.of(flowRequest, waterLevelRequest)))
                .thenReturn(List.of(latestWaterLevel, latestFlow));
        when(stationMapper.selectBatchIds(anyCollection()))
                .thenReturn(List.of(waterStation, flowStation));

        List<ObservationVO> result = observationService.getLatestObservations(List.of(flowRequest, waterLevelRequest));

        assertThat(result)
                .extracting(ObservationVO::getStationId, ObservationVO::getMetricType, ObservationVO::getStationCode, ObservationVO::getValue)
                .containsExactly(
                        tuple("station-flow", "FLOW", "ST_FLOW_CP_01", new BigDecimal("520.0")),
                        tuple("station-water", "WATER_LEVEL", "ST_WL_CP_01", new BigDecimal("4.35"))
                );
    }
}
