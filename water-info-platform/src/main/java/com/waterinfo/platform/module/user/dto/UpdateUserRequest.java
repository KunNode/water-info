package com.waterinfo.platform.module.user.dto;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.Size;
import lombok.Data;

/**
 * Update user request DTO
 */
@Data
public class UpdateUserRequest {

    @Size(max = 64, message = "Real name must not exceed 64 characters")
    private String realName;

    @Size(max = 32, message = "Phone must not exceed 32 characters")
    private String phone;

    @Email(message = "Invalid email format")
    @Size(max = 128, message = "Email must not exceed 128 characters")
    private String email;

    private String orgId;

    private String deptId;

    private String status;
}
