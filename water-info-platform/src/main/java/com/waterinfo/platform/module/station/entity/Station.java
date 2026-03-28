package com.waterinfo.platform.module.station.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * Station entity
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@TableName("station")
public class Station {

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String code;

    private String name;

    private String type;

    private String riverBasin;

    private String adminRegion;

    private BigDecimal lat;

    private BigDecimal lon;

    private BigDecimal elevation;

    private String status;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;
}
