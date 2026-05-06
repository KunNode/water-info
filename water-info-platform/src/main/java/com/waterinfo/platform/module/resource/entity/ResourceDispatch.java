package com.waterinfo.platform.module.resource.entity;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@TableName("resource_dispatch")
public class ResourceDispatch {

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String resourceId;
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

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;
}
