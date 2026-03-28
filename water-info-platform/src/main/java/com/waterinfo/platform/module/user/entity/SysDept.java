package com.waterinfo.platform.module.user.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

/**
 * Department entity
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@TableName("sys_dept")
public class SysDept {

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String orgId;

    private String name;

    private String parentId;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;
}
