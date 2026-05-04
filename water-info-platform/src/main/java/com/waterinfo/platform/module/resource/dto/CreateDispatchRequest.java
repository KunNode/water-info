package com.waterinfo.platform.module.resource.dto;

import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Data;

@Data
public class CreateDispatchRequest {

    @NotBlank(message = "资源ID不能为空")
    private String resourceId;

    private String planId;

    @NotNull(message = "调度数量不能为空")
    @Min(value = 1, message = "调度数量必须大于0")
    private Integer quantity;

    @NotBlank(message = "调出地点不能为空")
    private String fromLocation;

    @NotBlank(message = "调入地点不能为空")
    private String toLocation;

    private String source;

    private String notes;
}
