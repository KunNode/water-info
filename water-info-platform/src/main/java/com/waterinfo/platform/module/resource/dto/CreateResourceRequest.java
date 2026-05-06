package com.waterinfo.platform.module.resource.dto;

import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import lombok.Data;

import java.util.Map;

@Data
public class CreateResourceRequest {

    @NotBlank(message = "资源类型不能为空")
    private String type;

    @NotBlank(message = "资源名称不能为空")
    @Size(max = 100, message = "资源名称不超过100个字符")
    private String name;

    @NotNull(message = "数量不能为空")
    @Min(value = 0, message = "数量不能为负数")
    private Integer quantity;

    @NotBlank(message = "单位不能为空")
    @Size(max = 20, message = "单位不超过20个字符")
    private String unit;

    @NotBlank(message = "存放地点不能为空")
    @Size(max = 200, message = "存放地点不超过200个字符")
    private String location;

    private Map<String, Object> attributes;

    private String description;
}
