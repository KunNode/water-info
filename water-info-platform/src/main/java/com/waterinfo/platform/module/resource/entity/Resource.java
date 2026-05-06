package com.waterinfo.platform.module.resource.entity;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableLogic;
import com.baomidou.mybatisplus.annotation.TableName;
import com.waterinfo.platform.common.mybatis.typehandler.JsonbMapTypeHandler;
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
@TableName(value = "resource", autoResultMap = true)
public class Resource {

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String type;
    private String name;
    private Integer quantity;
    private String unit;
    private String location;
    private String status;

    @TableField(typeHandler = JsonbMapTypeHandler.class)
    private Map<String, Object> attributes;

    private String description;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;

    @TableLogic
    private Boolean deleted;
}
