package com.waterinfo.platform.observation;

import com.waterinfo.platform.module.alarm.entity.Alarm;
import com.waterinfo.platform.module.alarm.mapper.AlarmMapper;
import com.waterinfo.platform.module.alarm.service.AlarmService;
import com.waterinfo.platform.module.observation.dto.BatchObservationRequest;
import com.waterinfo.platform.module.observation.dto.BatchObservationResponse;
import com.waterinfo.platform.module.observation.service.ObservationService;
import com.waterinfo.platform.module.station.entity.Station;
import com.waterinfo.platform.module.station.mapper.StationMapper;
import com.waterinfo.platform.module.threshold.entity.ThresholdRule;
import com.waterinfo.platform.module.threshold.mapper.ThresholdRuleMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Integration tests for ObservationService with threshold evaluation
 */
@SpringBootTest
@Testcontainers
@ActiveProfiles("test")
class ObservationServiceTest {

    @Container
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:15-alpine")
            .withDatabaseName("water_info_test")
            .withUsername("test")
            .withPassword("test");

    @DynamicPropertySource
    static void configureProperties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", postgres::getJdbcUrl);
        registry.add("spring.datasource.username", postgres::getUsername);
        registry.add("spring.datasource.password", postgres::getPassword);
    }

    @Autowired
    private ObservationService observationService;

    @Autowired
    private StationMapper stationMapper;

    @Autowired
    private ThresholdRuleMapper thresholdRuleMapper;

    @Autowired
    private AlarmMapper alarmMapper;

    private Station testStation;
    private ThresholdRule warningRule;
    private ThresholdRule criticalRule;

    @BeforeEach
    void setUp() {
        // Clean up alarms
        alarmMapper.delete(null);
        
        // Create test station if not exists
        testStation = Station.builder()
                .code("TEST_STATION_001")
                .name("Test Station")
                .type("WATER_LEVEL")
                .status("ACTIVE")
                .lat(new BigDecimal("30.123456"))
                .lon(new BigDecimal("120.123456"))
                .build();
        stationMapper.insert(testStation);

        // Create threshold rules
        warningRule = ThresholdRule.builder()
                .stationId(testStation.getId())
                .metricType("WATER_LEVEL")
                .level("WARNING")
                .thresholdValue(new BigDecimal("10.0"))
                .enabled(true)
                .build();
        thresholdRuleMapper.insert(warningRule);

        criticalRule = ThresholdRule.builder()
                .stationId(testStation.getId())
                .metricType("WATER_LEVEL")
                .level("CRITICAL")
                .thresholdValue(new BigDecimal("15.0"))
                .enabled(true)
                .build();
        thresholdRuleMapper.insert(criticalRule);
    }

    @Test
    @DisplayName("Should create WARNING alarm when value exceeds warning threshold")
    void shouldCreateWarningAlarm_WhenValueExceedsWarningThreshold() {
        // Given
        BatchObservationRequest request = new BatchObservationRequest();
        BatchObservationRequest.ObservationItem item = new BatchObservationRequest.ObservationItem();
        item.setStationId(testStation.getId());
        item.setMetricType("WATER_LEVEL");
        item.setValue(new BigDecimal("12.5")); // Above warning threshold (10.0)
        item.setObservedAt(LocalDateTime.now());
        item.setUnit("m");
        request.setObservations(List.of(item));
        request.setRequestId("test-batch-001");

        // When
        BatchObservationResponse response = observationService.batchUpload(request);

        // Then
        assertEquals(1, response.getAccepted());
        assertEquals(0, response.getRejected());
        assertTrue(response.getAlarmsTriggered() >= 1);

        // Verify alarm was created
        List<Alarm> alarms = alarmMapper.selectList(null);
        assertTrue(alarms.stream().anyMatch(a -> 
                "WARNING".equals(a.getLevel()) && 
                AlarmService.STATUS_OPEN.equals(a.getStatus())));
    }

    @Test
    @DisplayName("Should create both WARNING and CRITICAL alarms when value exceeds both thresholds")
    void shouldCreateMultipleAlarms_WhenValueExceedsMultipleThresholds() {
        // Given
        BatchObservationRequest request = new BatchObservationRequest();
        BatchObservationRequest.ObservationItem item = new BatchObservationRequest.ObservationItem();
        item.setStationId(testStation.getId());
        item.setMetricType("WATER_LEVEL");
        item.setValue(new BigDecimal("18.0")); // Above both thresholds
        item.setObservedAt(LocalDateTime.now());
        item.setUnit("m");
        request.setObservations(List.of(item));
        request.setRequestId("test-batch-002");

        // When
        BatchObservationResponse response = observationService.batchUpload(request);

        // Then
        assertEquals(1, response.getAccepted());
        assertEquals(2, response.getAlarmsTriggered());

        // Verify both alarms were created
        List<Alarm> alarms = alarmMapper.selectList(null);
        assertTrue(alarms.stream().anyMatch(a -> "WARNING".equals(a.getLevel())));
        assertTrue(alarms.stream().anyMatch(a -> "CRITICAL".equals(a.getLevel())));
    }

    @Test
    @DisplayName("Should not create alarm when value is below threshold")
    void shouldNotCreateAlarm_WhenValueIsBelowThreshold() {
        // Given
        BatchObservationRequest request = new BatchObservationRequest();
        BatchObservationRequest.ObservationItem item = new BatchObservationRequest.ObservationItem();
        item.setStationId(testStation.getId());
        item.setMetricType("WATER_LEVEL");
        item.setValue(new BigDecimal("5.0")); // Below all thresholds
        item.setObservedAt(LocalDateTime.now());
        item.setUnit("m");
        request.setObservations(List.of(item));
        request.setRequestId("test-batch-003");

        // When
        BatchObservationResponse response = observationService.batchUpload(request);

        // Then
        assertEquals(1, response.getAccepted());
        assertEquals(0, response.getAlarmsTriggered());
    }

    @Test
    @DisplayName("Should update existing alarm when same threshold is exceeded again")
    void shouldUpdateExistingAlarm_WhenThresholdExceededAgain() {
        // Given - First observation triggers alarm
        BatchObservationRequest request1 = new BatchObservationRequest();
        BatchObservationRequest.ObservationItem item1 = new BatchObservationRequest.ObservationItem();
        item1.setStationId(testStation.getId());
        item1.setMetricType("WATER_LEVEL");
        item1.setValue(new BigDecimal("12.0"));
        item1.setObservedAt(LocalDateTime.now().minusMinutes(10));
        item1.setUnit("m");
        request1.setObservations(List.of(item1));
        request1.setRequestId("test-batch-004a");
        observationService.batchUpload(request1);

        // When - Second observation should update existing alarm
        BatchObservationRequest request2 = new BatchObservationRequest();
        BatchObservationRequest.ObservationItem item2 = new BatchObservationRequest.ObservationItem();
        item2.setStationId(testStation.getId());
        item2.setMetricType("WATER_LEVEL");
        item2.setValue(new BigDecimal("13.0"));
        item2.setObservedAt(LocalDateTime.now());
        item2.setUnit("m");
        request2.setObservations(List.of(item2));
        request2.setRequestId("test-batch-004b");
        BatchObservationResponse response = observationService.batchUpload(request2);

        // Then - Should still be only one WARNING alarm
        List<Alarm> alarms = alarmMapper.selectList(null);
        long warningCount = alarms.stream()
                .filter(a -> "WARNING".equals(a.getLevel()) && testStation.getId().equals(a.getStationId()))
                .count();
        assertEquals(1, warningCount);
    }

    @Test
    @DisplayName("Should handle batch with multiple observations")
    void shouldHandleBatchWithMultipleObservations() {
        // Given
        BatchObservationRequest request = new BatchObservationRequest();
        
        BatchObservationRequest.ObservationItem item1 = new BatchObservationRequest.ObservationItem();
        item1.setStationId(testStation.getId());
        item1.setMetricType("WATER_LEVEL");
        item1.setValue(new BigDecimal("5.0"));
        item1.setObservedAt(LocalDateTime.now().minusHours(2));
        item1.setUnit("m");

        BatchObservationRequest.ObservationItem item2 = new BatchObservationRequest.ObservationItem();
        item2.setStationId(testStation.getId());
        item2.setMetricType("WATER_LEVEL");
        item2.setValue(new BigDecimal("8.0"));
        item2.setObservedAt(LocalDateTime.now().minusHours(1));
        item2.setUnit("m");

        BatchObservationRequest.ObservationItem item3 = new BatchObservationRequest.ObservationItem();
        item3.setStationId(testStation.getId());
        item3.setMetricType("WATER_LEVEL");
        item3.setValue(new BigDecimal("12.0")); // Above warning threshold
        item3.setObservedAt(LocalDateTime.now());
        item3.setUnit("m");

        request.setObservations(List.of(item1, item2, item3));
        request.setRequestId("test-batch-005");

        // When
        BatchObservationResponse response = observationService.batchUpload(request);

        // Then
        assertEquals(3, response.getAccepted());
        assertEquals(0, response.getRejected());
        // Should trigger alarm based on the latest (highest) value
        assertTrue(response.getAlarmsTriggered() >= 1);
    }
}
