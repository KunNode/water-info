package com.waterinfo.platform.station;

import com.waterinfo.platform.common.exception.BusinessException;
import com.waterinfo.platform.common.exception.ErrorCode;
import com.waterinfo.platform.module.station.dto.CreateStationRequest;
import com.waterinfo.platform.module.station.dto.StationQueryRequest;
import com.waterinfo.platform.module.station.dto.UpdateStationRequest;
import com.waterinfo.platform.module.station.entity.Station;
import com.waterinfo.platform.module.station.mapper.StationMapper;
import com.waterinfo.platform.module.station.service.StationService;
import com.waterinfo.platform.module.station.vo.StationVO;
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

import static org.junit.jupiter.api.Assertions.*;

/**
 * Unit tests for StationService
 */
@SpringBootTest
@Testcontainers
@ActiveProfiles("test")
class StationServiceTest {

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
    private StationService stationService;

    @Autowired
    private StationMapper stationMapper;

    @BeforeEach
    void setUp() {
        stationMapper.delete(null);
    }

    @Test
    @DisplayName("Should create a new station successfully")
    void shouldCreateStationSuccessfully() {
        // Given
        CreateStationRequest request = new CreateStationRequest();
        request.setCode("STATION_001");
        request.setName("Test Station");
        request.setType("WATER_LEVEL");
        request.setRiverBasin("Yangtze River");
        request.setAdminRegion("Test Region");
        request.setLat(new BigDecimal("30.123456"));
        request.setLon(new BigDecimal("120.123456"));
        request.setElevation(new BigDecimal("50.0"));

        // When
        StationVO result = stationService.createStation(request);

        // Then
        assertNotNull(result.getId());
        assertEquals("STATION_001", result.getCode());
        assertEquals("Test Station", result.getName());
        assertEquals("WATER_LEVEL", result.getType());
        assertEquals("ACTIVE", result.getStatus());
    }

    @Test
    @DisplayName("Should throw exception when creating station with duplicate code")
    void shouldThrowException_WhenCreatingDuplicateStationCode() {
        // Given
        CreateStationRequest request1 = new CreateStationRequest();
        request1.setCode("DUPLICATE_TEST");
        request1.setName("First Station");
        request1.setType("WATER_LEVEL");
        stationService.createStation(request1);

        // When/Then
        CreateStationRequest request2 = new CreateStationRequest();
        request2.setCode("DUPLICATE_TEST");
        request2.setName("Second Station");
        request2.setType("WATER_LEVEL");

        BusinessException exception = assertThrows(BusinessException.class, () -> {
            stationService.createStation(request2);
        });
        assertEquals(ErrorCode.STATION_CODE_EXISTS.getCode(), exception.getCode());
    }

    @Test
    @DisplayName("Should throw exception for invalid station type")
    void shouldThrowException_ForInvalidStationType() {
        // Given
        CreateStationRequest request = new CreateStationRequest();
        request.setCode("STATION_TEST");
        request.setName("Test Station");
        request.setType("INVALID_TYPE");

        // When/Then
        BusinessException exception = assertThrows(BusinessException.class, () -> {
            stationService.createStation(request);
        });
        assertEquals(ErrorCode.PARAM_INVALID.getCode(), exception.getCode());
    }

    @Test
    @DisplayName("Should normalize station type aliases")
    void shouldNormalizeStationTypeAliases() {
        // Given - RAINFALL should be normalized to RAIN_GAUGE
        CreateStationRequest request = new CreateStationRequest();
        request.setCode("STATION_RAIN");
        request.setName("Rain Station");
        request.setType("RAINFALL");

        // When
        StationVO result = stationService.createStation(request);

        // Then
        assertEquals("RAIN_GAUGE", result.getType());
    }

    @Test
    @DisplayName("Should update station successfully")
    void shouldUpdateStationSuccessfully() {
        // Given - Create a station first
        CreateStationRequest createRequest = new CreateStationRequest();
        createRequest.setCode("STATION_UPDATE");
        createRequest.setName("Original Name");
        createRequest.setType("WATER_LEVEL");
        StationVO created = stationService.createStation(createRequest);

        // When - Update the station
        UpdateStationRequest updateRequest = new UpdateStationRequest();
        updateRequest.setName("Updated Name");
        updateRequest.setRiverBasin("Updated River Basin");
        StationVO result = stationService.updateStation(created.getId(), updateRequest);

        // Then
        assertEquals("Updated Name", result.getName());
        assertEquals("Updated River Basin", result.getRiverBasin());
    }

    @Test
    @DisplayName("Should throw exception when updating non-existent station")
    void shouldThrowException_WhenUpdatingNonExistentStation() {
        // Given
        UpdateStationRequest request = new UpdateStationRequest();
        request.setName("Non Existent");

        // When/Then
        BusinessException exception = assertThrows(BusinessException.class, () -> {
            stationService.updateStation("non-existent-id", request);
        });
        assertEquals(ErrorCode.STATION_NOT_FOUND.getCode(), exception.getCode());
    }

    @Test
    @DisplayName("Should get station by ID")
    void shouldGetStationById() {
        // Given
        CreateStationRequest createRequest = new CreateStationRequest();
        createRequest.setCode("STATION_GET");
        createRequest.setName("Get Test Station");
        createRequest.setType("RESERVOIR");
        StationVO created = stationService.createStation(createRequest);

        // When
        StationVO result = stationService.getStationById(created.getId());

        // Then
        assertEquals(created.getId(), result.getId());
        assertEquals("STATION_GET", result.getCode());
    }

    @Test
    @DisplayName("Should query stations with pagination")
    void shouldQueryStationsWithPagination() {
        // Given - Create multiple stations
        for (int i = 0; i < 25; i++) {
            CreateStationRequest request = new CreateStationRequest();
            request.setCode("STATION_PAGINATION_" + i);
            request.setName("Pagination Test " + i);
            request.setType("WATER_LEVEL");
            stationService.createStation(request);
        }

        // When - Query with pagination
        StationQueryRequest queryRequest = new StationQueryRequest();
        queryRequest.setPage(1);
        queryRequest.setSize(10);

        var result = stationService.queryStations(queryRequest);

        // Then
        assertEquals(10, result.getRecords().size());
        assertEquals(25L, result.getTotal());
        assertEquals(3, result.getPages());
    }

    @Test
    @DisplayName("Should query stations with filters")
    void shouldQueryStationsWithFilters() {
        // Given - Create stations with different types
        CreateStationRequest request1 = new CreateStationRequest();
        request1.setCode("STATION_FILTER_1");
        request1.setName("Filter Test 1");
        request1.setType("WATER_LEVEL");
        request1.setAdminRegion("Region A");
        stationService.createStation(request1);

        CreateStationRequest request2 = new CreateStationRequest();
        request2.setCode("STATION_FILTER_2");
        request2.setName("Filter Test 2");
        request2.setType("RAIN_GAUGE");
        request2.setAdminRegion("Region B");
        stationService.createStation(request2);

        // When - Query with type filter
        StationQueryRequest queryRequest = new StationQueryRequest();
        queryRequest.setPage(1);
        queryRequest.setSize(10);
        queryRequest.setType("WATER_LEVEL");

        var result = stationService.queryStations(queryRequest);

        // Then
        assertEquals(1, result.getRecords().size());
        assertEquals("WATER_LEVEL", result.getRecords().get(0).getType());
    }

    @Test
    @DisplayName("Should delete station successfully")
    void shouldDeleteStationSuccessfully() {
        // Given
        CreateStationRequest request = new CreateStationRequest();
        request.setCode("STATION_DELETE");
        request.setName("Delete Test");
        request.setType("WATER_LEVEL");
        StationVO created = stationService.createStation(request);

        // When
        stationService.deleteStation(created.getId());

        // Then - Verify station is deleted
        assertThrows(BusinessException.class, () -> {
            stationService.getStationById(created.getId());
        });
    }

    @Test
    @DisplayName("Should check if station code exists")
    void shouldCheckIfStationCodeExists() {
        // Given
        CreateStationRequest request = new CreateStationRequest();
        request.setCode("STATION_EXISTS_CHECK");
        request.setName("Exists Check");
        request.setType("WATER_LEVEL");
        stationService.createStation(request);

        // When
        boolean exists = stationService.existsByCode("STATION_EXISTS_CHECK");
        boolean notExists = stationService.existsByCode("NON_EXISTENT_CODE");

        // Then
        assertTrue(exists);
        assertFalse(notExists);
    }
}
