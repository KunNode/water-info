package com.waterinfo.platform.module.resource.vo;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ResourceDispatchVO {

    private String id;
    private String resourceId;
    private String resourceName;
    private String resourceType;
    private String planId;
    private Integer quantity;
    private String fromLocation;
    private String toLocation;
    private String status;
    private LocalDateTime dispatchedAt;
    private LocalDateTime arrivedAt;
    private LocalDateTime returnedAt;
    private String operator;
    private String source;
    private String notes;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
