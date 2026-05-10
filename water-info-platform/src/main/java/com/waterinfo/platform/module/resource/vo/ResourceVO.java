package com.waterinfo.platform.module.resource.vo;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.Map;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ResourceVO {

    private String id;
    private String type;
    private String name;
    private Integer quantity;
    private String unit;
    private String location;
    private String status;
    private Map<String, Object> attributes;
    private String description;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
