package com.waterinfo.platform.module.resource.dto;

import lombok.Data;

import java.util.Map;

@Data
public class UpdateResourceRequest {

    private String name;
    private Integer quantity;
    private String unit;
    private String location;
    private String status;
    private Map<String, Object> attributes;
    private String description;
}
