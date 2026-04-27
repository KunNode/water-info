package com.waterinfo.platform.common.exception;

import com.waterinfo.platform.common.api.ApiResponse;
import jakarta.servlet.http.HttpServletRequest;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class GlobalExceptionHandlerTest {

    @Test
    void businessAuthFailuresUseHttpUnauthorized() {
        GlobalExceptionHandler handler = new GlobalExceptionHandler();
        HttpServletRequest request = mock(HttpServletRequest.class);
        when(request.getRequestURI()).thenReturn("/api/v1/auth/login");

        ResponseEntity<ApiResponse<Object>> response = handler.handleBusinessException(
                new BusinessException(ErrorCode.AUTH_INVALID_CREDENTIALS),
                request
        );

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.UNAUTHORIZED);
        assertThat(response.getBody()).isNotNull();
        assertThat(response.getBody().getCode()).isEqualTo(ErrorCode.AUTH_INVALID_CREDENTIALS.getCode());
    }

    @Test
    void duplicateBusinessFailuresUseHttpConflict() {
        GlobalExceptionHandler handler = new GlobalExceptionHandler();
        HttpServletRequest request = mock(HttpServletRequest.class);
        when(request.getRequestURI()).thenReturn("/api/v1/stations");

        ResponseEntity<ApiResponse<Object>> response = handler.handleBusinessException(
                new BusinessException(ErrorCode.STATION_CODE_EXISTS),
                request
        );

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.CONFLICT);
    }
}
