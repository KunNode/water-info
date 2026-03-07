package com.waterinfo.platform.module.user.dto;

import jakarta.validation.constraints.NotEmpty;
import lombok.Data;

import java.util.List;

/**
 * Set user roles request DTO
 */
@Data
public class SetUserRolesRequest {

    @NotEmpty(message = "Role IDs cannot be empty")
    private List<String> roleIds;
}
