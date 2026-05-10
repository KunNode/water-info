package com.waterinfo.platform.module.resource.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

@Data
public class UpdateDispatchStatusRequest {

    @NotBlank(message = "状态不能为空")
    private String status;

    private String notes;
}
