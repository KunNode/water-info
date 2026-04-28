package com.waterinfo.platform.module.aiassessment.entity;

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
@TableName("ai_assessment")
public class AiAssessment {

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String stationId;

    private String metricType;

    private String level;

    private String summary;

    private String planExcerpt;

    private String source;

    private LocalDateTime assessedAt;

    private LocalDateTime assessedAtMinute;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;
}
