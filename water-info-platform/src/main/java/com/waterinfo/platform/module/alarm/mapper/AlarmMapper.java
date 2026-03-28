package com.waterinfo.platform.module.alarm.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.waterinfo.platform.module.alarm.entity.Alarm;
import org.apache.ibatis.annotations.Mapper;

/**
 * Alarm mapper
 */
@Mapper
public interface AlarmMapper extends BaseMapper<Alarm> {
}
