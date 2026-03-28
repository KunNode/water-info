package com.waterinfo.platform.module.sensor.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.waterinfo.platform.module.sensor.entity.Sensor;
import org.apache.ibatis.annotations.Mapper;

/**
 * Sensor mapper
 */
@Mapper
public interface SensorMapper extends BaseMapper<Sensor> {
}
