package com.waterinfo.platform.module.user.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Data;

/**
 * Change password request DTO
 */
@Data
public class ChangePasswordRequest {

    private String currentPassword;

    @NotBlank(message = "New password is required")
    @Size(min = 6, max = 64, message = "Password must be 6-64 characters")
    private String newPassword;
}
