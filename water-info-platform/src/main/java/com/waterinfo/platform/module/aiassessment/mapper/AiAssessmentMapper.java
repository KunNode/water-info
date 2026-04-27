package com.waterinfo.platform.module.aiassessment.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.waterinfo.platform.module.aiassessment.entity.AiAssessment;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface AiAssessmentMapper extends BaseMapper<AiAssessment> {

    @Insert("""
            INSERT INTO ai_assessment (
                id, station_id, metric_type, level, summary, plan_excerpt,
                source, assessed_at, assessed_at_minute, created_at
            )
            VALUES (
                #{id}, #{stationId}, #{metricType}, #{level}, #{summary}, #{planExcerpt},
                #{source}, #{assessedAt}, #{assessedAtMinute}, CURRENT_TIMESTAMP
            )
            ON CONFLICT (station_id, source, assessed_at_minute)
            DO UPDATE SET
                metric_type = EXCLUDED.metric_type,
                level = EXCLUDED.level,
                summary = EXCLUDED.summary,
                plan_excerpt = EXCLUDED.plan_excerpt,
                assessed_at = EXCLUDED.assessed_at
            """)
    int upsert(AiAssessment assessment);
}
