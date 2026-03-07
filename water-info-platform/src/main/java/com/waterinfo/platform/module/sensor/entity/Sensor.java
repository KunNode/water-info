package com.waterinfo.platform.module.sensor.entity;

import com.baomidou.mybatisplus.annotation.*;
import com.waterinfo.platform.common.mybatis.typehandler.JsonbMapTypeHandler;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.Map;

/**
 * Sensor entity
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@TableName(value = "sensor", autoResultMap = true)
public class Sensor {

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String stationId;

    private String type;

    private String unit;

    private Integer samplingIntervalSec;

    private String status;

    private LocalDateTime lastSeenAt;

    @TableField(typeHandler = JsonbMapTypeHandler.class)
    private Map<String, Object> meta;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;
}
