package com.waterinfo.platform.module.observation.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.waterinfo.platform.module.observation.entity.Observation;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

/**
 * Observation mapper with batch insert support
 */
@Mapper
public interface ObservationMapper extends BaseMapper<Observation> {

    /**
     * Batch insert observations (optimized)
     */
    @Insert("<script>" +
            "INSERT INTO observation (id, station_id, metric_type, value, unit, observed_at, quality_flag, source, request_id, created_at) VALUES " +
            "<foreach collection='list' item='item' separator=','>" +
            "(#{item.id}, #{item.stationId}, #{item.metricType}, #{item.value}, #{item.unit}, #{item.observedAt}, #{item.qualityFlag}, #{item.source}, #{item.requestId}, #{item.createdAt})" +
            "</foreach>" +
            "</script>")
    int batchInsert(@Param("list") List<Observation> observations);
}
