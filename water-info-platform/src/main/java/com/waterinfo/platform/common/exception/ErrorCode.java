package com.waterinfo.platform.common.exception;

import lombok.Getter;

/**
 * Error codes enumeration
 */
@Getter
public enum ErrorCode {

    // Common errors (1000-1099)
    SUCCESS(200, "Success"),
    BAD_REQUEST(400, "Bad request"),
    UNAUTHORIZED(401, "Unauthorized"),
    FORBIDDEN(403, "Access denied"),
    NOT_FOUND(404, "Resource not found"),
    METHOD_NOT_ALLOWED(405, "Method not allowed"),
    INTERNAL_ERROR(500, "Internal server error"),

    // Validation errors (1100-1199)
    VALIDATION_ERROR(1100, "Validation error"),
    PARAM_MISSING(1101, "Required parameter missing"),
    PARAM_INVALID(1102, "Invalid parameter"),

    // Authentication errors (1200-1299)
    AUTH_INVALID_CREDENTIALS(1200, "Invalid username or password"),
    AUTH_TOKEN_EXPIRED(1201, "Token expired"),
    AUTH_TOKEN_INVALID(1202, "Invalid token"),
    AUTH_USER_DISABLED(1203, "User account is disabled"),
    AUTH_USER_LOCKED(1204, "User account is locked"),

    // User errors (1300-1399)
    USER_NOT_FOUND(1300, "User not found"),
    USER_ALREADY_EXISTS(1301, "User already exists"),
    USER_PASSWORD_INCORRECT(1302, "Current password is incorrect"),
    USER_ROLE_NOT_FOUND(1303, "Role not found"),

    // Station errors (1400-1499)
    STATION_NOT_FOUND(1400, "Station not found"),
    STATION_CODE_EXISTS(1401, "Station code already exists"),

    // Sensor errors (1500-1599)
    SENSOR_NOT_FOUND(1500, "Sensor not found"),

    // Observation errors (1600-1699)
    OBSERVATION_BATCH_TOO_LARGE(1600, "Batch size exceeds limit"),
    OBSERVATION_INVALID_DATA(1601, "Invalid observation data"),

    // Threshold errors (1700-1799)
    THRESHOLD_NOT_FOUND(1700, "Threshold rule not found"),

    // Alarm errors (1800-1899)
    ALARM_NOT_FOUND(1800, "Alarm not found"),
    ALARM_INVALID_STATE_TRANSITION(1801, "Invalid alarm state transition"),
    ALARM_ALREADY_CLOSED(1802, "Alarm is already closed"),

    // Organization errors (1900-1999)
    ORG_NOT_FOUND(1900, "Organization not found"),
    ORG_CODE_EXISTS(1901, "Organization code already exists"),
    DEPT_NOT_FOUND(1902, "Department not found");

    private final Integer code;
    private final String message;

    ErrorCode(Integer code, String message) {
        this.code = code;
        this.message = message;
    }
}
