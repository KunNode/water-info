package com.waterinfo.platform.module.audit.entity;

import com.baomidou.mybatisplus.annotation.*;
import com.waterinfo.platform.common.mybatis.typehandler.JsonbMapTypeHandler;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.Map;

/**
 * Audit log entity
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@TableName(value = "sys_audit_log", autoResultMap = true)
public class SysAuditLog {

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String actorUserId;

    private String actorUsername;

    private String action;

    private String targetType;

    private String targetId;

    @TableField(typeHandler = JsonbMapTypeHandler.class)
    private Map<String, Object> detail;

    private String ip;

    private String userAgent;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;
}
