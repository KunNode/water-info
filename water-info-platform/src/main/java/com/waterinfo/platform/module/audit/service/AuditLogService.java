package com.waterinfo.platform.module.audit.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.waterinfo.platform.common.api.PageRequest;
import com.waterinfo.platform.module.audit.entity.SysAuditLog;
import com.waterinfo.platform.module.audit.mapper.SysAuditLogMapper;
import com.waterinfo.platform.security.SecurityUser;
import jakarta.servlet.http.HttpServletRequest;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Async;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;
import org.springframework.web.context.request.RequestContextHolder;
import org.springframework.web.context.request.ServletRequestAttributes;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.Map;

/**
 * Audit log service
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AuditLogService extends ServiceImpl<SysAuditLogMapper, SysAuditLog> {

    /**
     * Log an audit event asynchronously
     */
    @Async
    public void logAsync(String action, String targetType, String targetId, Map<String, Object> detail) {
        try {
            log(action, targetType, targetId, detail);
        } catch (Exception e) {
            log.error("Failed to log audit event: {}", e.getMessage(), e);
        }
    }

    /**
     * Log an audit event
     */
    public void log(String action, String targetType, String targetId, Map<String, Object> detail) {
        SysAuditLog auditLog = SysAuditLog.builder()
                .action(action)
                .targetType(targetType)
                .targetId(targetId)
                .detail(sanitizeDetail(detail))
                .createdAt(LocalDateTime.now())
                .build();

        // Get current user info
        Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
        if (authentication != null && authentication.getPrincipal() instanceof SecurityUser user) {
            auditLog.setActorUserId(user.getId());
            auditLog.setActorUsername(user.getUsername());
        }

        // Get request info
        try {
            ServletRequestAttributes attrs = (ServletRequestAttributes) RequestContextHolder.getRequestAttributes();
            if (attrs != null) {
                HttpServletRequest request = attrs.getRequest();
                auditLog.setIp(getClientIp(request));
                auditLog.setUserAgent(request.getHeader("User-Agent"));
            }
        } catch (Exception e) {
            log.debug("Could not get request info for audit log: {}", e.getMessage());
        }

        save(auditLog);
        log.info("AUDIT: action={}, targetType={}, targetId={}, user={}", 
                action, targetType, targetId, auditLog.getActorUsername());
    }

    /**
     * Query audit logs with pagination
     */
    public Page<SysAuditLog> queryAuditLogs(PageRequest pageRequest, String action, 
                                            String actorUserId, LocalDateTime start, LocalDateTime end) {
        Page<SysAuditLog> page = new Page<>(pageRequest.getPage(), pageRequest.getSize());
        
        LambdaQueryWrapper<SysAuditLog> wrapper = new LambdaQueryWrapper<>();
        
        if (StringUtils.hasText(action)) {
            wrapper.eq(SysAuditLog::getAction, action);
        }
        if (StringUtils.hasText(actorUserId)) {
            wrapper.eq(SysAuditLog::getActorUserId, actorUserId);
        }
        if (start != null) {
            wrapper.ge(SysAuditLog::getCreatedAt, start);
        }
        if (end != null) {
            wrapper.le(SysAuditLog::getCreatedAt, end);
        }
        
        wrapper.orderByDesc(SysAuditLog::getCreatedAt);
        
        return page(page, wrapper);
    }

    /**
     * Sanitize detail map to remove sensitive information
     */
    private Map<String, Object> sanitizeDetail(Map<String, Object> detail) {
        if (detail == null) {
            return null;
        }
        
        Map<String, Object> sanitized = new HashMap<>(detail);
        // Remove sensitive fields
        sanitized.remove("password");
        sanitized.remove("passwordHash");
        sanitized.remove("token");
        sanitized.remove("accessToken");
        sanitized.remove("refreshToken");
        sanitized.remove("secret");
        
        return sanitized;
    }

    /**
     * Get client IP address from request
     */
    private String getClientIp(HttpServletRequest request) {
        String ip = request.getHeader("X-Forwarded-For");
        if (!StringUtils.hasText(ip) || "unknown".equalsIgnoreCase(ip)) {
            ip = request.getHeader("X-Real-IP");
        }
        if (!StringUtils.hasText(ip) || "unknown".equalsIgnoreCase(ip)) {
            ip = request.getHeader("Proxy-Client-IP");
        }
        if (!StringUtils.hasText(ip) || "unknown".equalsIgnoreCase(ip)) {
            ip = request.getRemoteAddr();
        }
        // Handle multiple IPs (take the first one)
        if (ip != null && ip.contains(",")) {
            ip = ip.split(",")[0].trim();
        }
        return ip;
    }
}
