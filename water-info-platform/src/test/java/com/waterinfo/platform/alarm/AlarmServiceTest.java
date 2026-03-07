package com.waterinfo.platform.alarm;

import com.waterinfo.platform.common.exception.BusinessException;
import com.waterinfo.platform.common.exception.ErrorCode;
import com.waterinfo.platform.module.alarm.entity.Alarm;
import com.waterinfo.platform.module.alarm.mapper.AlarmMapper;
import com.waterinfo.platform.module.alarm.service.AlarmService;
import com.waterinfo.platform.module.station.entity.Station;
import com.waterinfo.platform.module.station.mapper.StationMapper;
import com.waterinfo.platform.module.user.entity.SysUser;
import com.waterinfo.platform.module.user.mapper.SysUserMapper;
import com.waterinfo.platform.security.SecurityUser;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;
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
 * Integration tests for AlarmService state machine validation
 */
@SpringBootTest
@Testcontainers
@ActiveProfiles("test")
class AlarmServiceTest {

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
    private AlarmService alarmService;

    @Autowired
    private AlarmMapper alarmMapper;

    @Autowired
    private StationMapper stationMapper;

    @Autowired
    private SysUserMapper userMapper;

    private Station testStation;
    private SysUser testUser;

    @BeforeEach
    void setUp() {
        // Clean up alarms
        alarmMapper.delete(null);

        // Create test station if not exists
        testStation = Station.builder()
                .code("ALARM_TEST_STATION")
                .name("Alarm Test Station")
                .type("WATER_LEVEL")
                .status("ACTIVE")
                .lat(new BigDecimal("30.123456"))
                .lon(new BigDecimal("120.123456"))
                .build();
        stationMapper.insert(testStation);

        // Create test user if not exists
        testUser = SysUser.builder()
                .username("alarm_test_user")
                .passwordHash("$2a$10$test")
                .realName("Alarm Test User")
                .status("ACTIVE")
                .deleted(0)
                .build();
        userMapper.insert(testUser);

        // Set up security context
        SecurityUser securityUser = SecurityUser.builder()
                .id(testUser.getId())
                .username(testUser.getUsername())
                .realName(testUser.getRealName())
                .roles(List.of("OPERATOR"))
                .enabled(true)
                .accountNonLocked(true)
                .build();
        UsernamePasswordAuthenticationToken authentication = 
                new UsernamePasswordAuthenticationToken(securityUser, null, securityUser.getAuthorities());
        SecurityContextHolder.getContext().setAuthentication(authentication);
    }

    @Test
    @DisplayName("Valid transition: OPEN -> ACK")
    void shouldAllowTransition_OpenToAck() {
        // Given
        Alarm alarm = createOpenAlarm();

        // When
        var result = alarmService.acknowledgeAlarm(alarm.getId());

        // Then
        assertEquals(AlarmService.STATUS_ACK, result.getStatus());
        assertNotNull(result.getAcknowledgedAt());
        assertEquals(testUser.getId(), result.getAcknowledgedBy());
    }

    @Test
    @DisplayName("Valid transition: ACK -> CLOSED")
    void shouldAllowTransition_AckToClosed() {
        // Given
        Alarm alarm = createOpenAlarm();
        alarmService.acknowledgeAlarm(alarm.getId()); // First transition to ACK

        // When
        var result = alarmService.closeAlarm(alarm.getId());

        // Then
        assertEquals(AlarmService.STATUS_CLOSED, result.getStatus());
        assertNotNull(result.getClosedAt());
        assertEquals(testUser.getId(), result.getClosedBy());
    }

    @Test
    @DisplayName("Valid transition: OPEN -> CLOSED (skip ACK)")
    void shouldAllowTransition_OpenToClosed() {
        // Given
        Alarm alarm = createOpenAlarm();

        // When
        var result = alarmService.closeAlarm(alarm.getId());

        // Then
        assertEquals(AlarmService.STATUS_CLOSED, result.getStatus());
        assertNotNull(result.getClosedAt());
    }

    @Test
    @DisplayName("Invalid transition: ACK -> OPEN should throw exception")
    void shouldThrowException_AckToOpen() {
        // Given
        Alarm alarm = createOpenAlarm();
        alarmService.acknowledgeAlarm(alarm.getId()); // Transition to ACK

        // When/Then - Trying to acknowledge again should fail
        BusinessException exception = assertThrows(BusinessException.class, () -> {
            alarmService.acknowledgeAlarm(alarm.getId());
        });

        assertEquals(ErrorCode.ALARM_INVALID_STATE_TRANSITION.getCode(), exception.getCode());
    }

    @Test
    @DisplayName("Invalid transition: CLOSED -> ACK should throw exception")
    void shouldThrowException_ClosedToAck() {
        // Given
        Alarm alarm = createOpenAlarm();
        alarmService.closeAlarm(alarm.getId()); // Transition to CLOSED

        // When/Then
        BusinessException exception = assertThrows(BusinessException.class, () -> {
            alarmService.acknowledgeAlarm(alarm.getId());
        });

        assertEquals(ErrorCode.ALARM_INVALID_STATE_TRANSITION.getCode(), exception.getCode());
    }

    @Test
    @DisplayName("Invalid transition: CLOSED -> CLOSED should throw exception")
    void shouldThrowException_ClosedToClosed() {
        // Given
        Alarm alarm = createOpenAlarm();
        alarmService.closeAlarm(alarm.getId()); // Transition to CLOSED

        // When/Then
        BusinessException exception = assertThrows(BusinessException.class, () -> {
            alarmService.closeAlarm(alarm.getId());
        });

        assertEquals(ErrorCode.ALARM_ALREADY_CLOSED.getCode(), exception.getCode());
    }

    @Test
    @DisplayName("Should create new alarm when createOrUpdateAlarm called with no existing alarm")
    void shouldCreateNewAlarm_WhenNoExistingAlarm() {
        // When
        Alarm alarm = alarmService.createOrUpdateAlarm(
                testStation.getId(),
                "WATER_LEVEL",
                "WARNING",
                LocalDateTime.now(),
                "Test message"
        );

        // Then
        assertNotNull(alarm.getId());
        assertEquals(AlarmService.STATUS_OPEN, alarm.getStatus());
        assertEquals("WARNING", alarm.getLevel());
    }

    @Test
    @DisplayName("Should update existing alarm when createOrUpdateAlarm called with existing OPEN alarm")
    void shouldUpdateExistingAlarm_WhenOpenAlarmExists() {
        // Given
        LocalDateTime firstTime = LocalDateTime.now().minusHours(1);
        Alarm existingAlarm = alarmService.createOrUpdateAlarm(
                testStation.getId(),
                "WATER_LEVEL",
                "WARNING",
                firstTime,
                "First message"
        );

        // When
        LocalDateTime secondTime = LocalDateTime.now();
        Alarm updatedAlarm = alarmService.createOrUpdateAlarm(
                testStation.getId(),
                "WATER_LEVEL",
                "WARNING",
                secondTime,
                "Updated message"
        );

        // Then
        assertEquals(existingAlarm.getId(), updatedAlarm.getId()); // Same alarm
        assertEquals("Updated message", updatedAlarm.getMessage());
        assertEquals(secondTime, updatedAlarm.getLastTriggerAt());
    }

    @Test
    @DisplayName("Full lifecycle: OPEN -> ACK -> CLOSED")
    void shouldCompleteFullLifecycle() {
        // Given
        Alarm alarm = createOpenAlarm();
        assertEquals(AlarmService.STATUS_OPEN, alarm.getStatus());

        // When - Acknowledge
        var ackedAlarm = alarmService.acknowledgeAlarm(alarm.getId());
        assertEquals(AlarmService.STATUS_ACK, ackedAlarm.getStatus());
        assertNotNull(ackedAlarm.getAcknowledgedAt());
        assertNull(ackedAlarm.getClosedAt());

        // When - Close
        var closedAlarm = alarmService.closeAlarm(alarm.getId());
        assertEquals(AlarmService.STATUS_CLOSED, closedAlarm.getStatus());
        assertNotNull(closedAlarm.getAcknowledgedAt());
        assertNotNull(closedAlarm.getClosedAt());
        assertNotNull(closedAlarm.getEndAt());
    }

    private Alarm createOpenAlarm() {
        Alarm alarm = Alarm.builder()
                .stationId(testStation.getId())
                .metricType("WATER_LEVEL")
                .level("WARNING")
                .startAt(LocalDateTime.now())
                .lastTriggerAt(LocalDateTime.now())
                .status(AlarmService.STATUS_OPEN)
                .message("Test alarm")
                .build();
        alarmMapper.insert(alarm);
        return alarm;
    }
}
