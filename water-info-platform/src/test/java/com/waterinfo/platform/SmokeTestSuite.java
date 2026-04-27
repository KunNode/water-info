package com.waterinfo.platform;

import com.waterinfo.platform.common.api.ApiResponse;
import com.waterinfo.platform.common.exception.BusinessException;
import com.waterinfo.platform.common.exception.ErrorCode;
import com.waterinfo.platform.common.exception.GlobalExceptionHandler;
import jakarta.servlet.http.HttpServletRequest;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class SmokeTestSuite {

    @Test
    void authFailuresReturnUnauthorizedHttpStatus() {
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
}
