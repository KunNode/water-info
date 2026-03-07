package com.waterinfo.platform.module.audit.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.waterinfo.platform.module.audit.entity.SysAuditLog;
import org.apache.ibatis.annotations.Mapper;

/**
 * Audit log mapper
 */
@Mapper
public interface SysAuditLogMapper extends BaseMapper<SysAuditLog> {
}
