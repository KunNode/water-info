package com.waterinfo.platform.module.resource.vo;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ResourceStatsVO {

    private String type;
    private String status;
    private Long count;
    private Integer totalQuantity;
}
