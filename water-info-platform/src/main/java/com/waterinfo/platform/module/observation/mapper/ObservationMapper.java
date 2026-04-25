package com.waterinfo.platform.module.observation.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.waterinfo.platform.module.observation.entity.Observation;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.util.List;
import java.time.LocalDateTime;

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

    @Select("<script>" +
            "SELECT id, station_id, metric_type, value, unit, observed_at, quality_flag, source, request_id, created_at " +
            "FROM (" +
            "  SELECT o.id, o.station_id, o.metric_type, o.value, o.unit, o.observed_at, o.quality_flag, o.source, o.request_id, o.created_at, " +
            "         ROW_NUMBER() OVER (PARTITION BY o.station_id, o.metric_type ORDER BY o.observed_at DESC) AS rn " +
            "  FROM observation o " +
            "  WHERE o.observed_at &gt;= #{since} AND " +
            "  <foreach collection='items' item='item' separator=' OR ' open='(' close=')'>" +
            "    (o.station_id = #{item.stationId} AND o.metric_type = #{item.metricType})" +
            "  </foreach>" +
            ") latest " +
            "WHERE latest.rn = 1" +
            "</script>")
    List<Observation> selectLatestByStationMetricPairs(@Param("items") List<?> items,
                                                       @Param("since") LocalDateTime since);

    default List<Observation> selectLatestByStationMetricPairs(List<?> items) {
        return selectLatestByStationMetricPairs(items, LocalDateTime.of(1970, 1, 1, 0, 0));
    }
}
