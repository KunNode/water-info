package com.waterinfo.platform.module.user.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.waterinfo.platform.common.api.PageRequest;
import com.waterinfo.platform.common.exception.BusinessException;
import com.waterinfo.platform.common.exception.ErrorCode;
import com.waterinfo.platform.module.audit.service.AuditLogService;
import com.waterinfo.platform.module.user.dto.ChangePasswordRequest;
import com.waterinfo.platform.module.user.dto.CreateUserRequest;
import com.waterinfo.platform.module.user.dto.UpdateUserRequest;
import com.waterinfo.platform.module.user.entity.*;
import com.waterinfo.platform.module.user.mapper.*;
import com.waterinfo.platform.module.user.vo.UserVO;
import com.waterinfo.platform.security.SecurityUser;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * User service
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class UserService extends ServiceImpl<SysUserMapper, SysUser> {

    private final SysUserMapper userMapper;
    private final SysRoleMapper roleMapper;
    private final SysUserRoleMapper userRoleMapper;
    private final SysOrgMapper orgMapper;
    private final SysDeptMapper deptMapper;
    private final PasswordEncoder passwordEncoder;
    private final AuditLogService auditLogService;

    /**
     * Create a new user
     */
    @Transactional
    public UserVO createUser(CreateUserRequest request) {
        // Check if username exists
        if (existsByUsername(request.getUsername())) {
            throw new BusinessException(ErrorCode.USER_ALREADY_EXISTS);
        }

        SysUser user = SysUser.builder()
                .username(request.getUsername())
                .passwordHash(passwordEncoder.encode(request.getPassword()))
                .realName(request.getRealName())
                .phone(request.getPhone())
                .email(request.getEmail())
                .orgId(request.getOrgId())
                .deptId(request.getDeptId())
                .status("ACTIVE")
                .passwordUpdatedAt(LocalDateTime.now())
                .deleted(0)
                .build();

        save(user);

        auditLogService.logAsync("USER_CREATE", "USER", user.getId(), 
                Map.of("username", user.getUsername()));

        return convertToVO(user);
    }

    /**
     * Update user
     */
    @Transactional
    public UserVO updateUser(String id, UpdateUserRequest request) {
        SysUser user = getById(id);
        if (user == null || user.getDeleted() == 1) {
            throw new BusinessException(ErrorCode.USER_NOT_FOUND);
        }

        if (StringUtils.hasText(request.getRealName())) {
            user.setRealName(request.getRealName());
        }
        if (StringUtils.hasText(request.getPhone())) {
            user.setPhone(request.getPhone());
        }
        if (StringUtils.hasText(request.getEmail())) {
            user.setEmail(request.getEmail());
        }
        if (StringUtils.hasText(request.getOrgId())) {
            user.setOrgId(request.getOrgId());
        }
        if (StringUtils.hasText(request.getDeptId())) {
            user.setDeptId(request.getDeptId());
        }
        if (StringUtils.hasText(request.getStatus())) {
            user.setStatus(request.getStatus());
        }

        updateById(user);

        auditLogService.logAsync("USER_UPDATE", "USER", user.getId(), 
                Map.of("username", user.getUsername()));

        return convertToVO(user);
    }

    /**
     * Change user password
     */
    @Transactional
    public void changePassword(String id, ChangePasswordRequest request, boolean isAdmin) {
        SysUser user = getById(id);
        if (user == null || user.getDeleted() == 1) {
            throw new BusinessException(ErrorCode.USER_NOT_FOUND);
        }

        // If not admin reset, verify current password
        if (!isAdmin && StringUtils.hasText(request.getCurrentPassword())) {
            if (!passwordEncoder.matches(request.getCurrentPassword(), user.getPasswordHash())) {
                throw new BusinessException(ErrorCode.USER_PASSWORD_INCORRECT);
            }
        }

        user.setPasswordHash(passwordEncoder.encode(request.getNewPassword()));
        user.setPasswordUpdatedAt(LocalDateTime.now());
        updateById(user);

        auditLogService.logAsync("PASSWORD_RESET", "USER", user.getId(), 
                Map.of("username", user.getUsername(), "isAdminReset", isAdmin));
    }

    /**
     * Set user roles
     */
    @Transactional
    public void setUserRoles(String userId, List<String> roleIds) {
        SysUser user = getById(userId);
        if (user == null || user.getDeleted() == 1) {
            throw new BusinessException(ErrorCode.USER_NOT_FOUND);
        }

        // Verify all roles exist
        for (String roleId : roleIds) {
            if (roleMapper.selectById(roleId) == null) {
                throw new BusinessException(ErrorCode.USER_ROLE_NOT_FOUND, "Role not found: " + roleId);
            }
        }

        // Delete existing roles
        userRoleMapper.delete(new LambdaQueryWrapper<SysUserRole>()
                .eq(SysUserRole::getUserId, userId));

        // Add new roles
        for (String roleId : roleIds) {
            SysUserRole userRole = SysUserRole.builder()
                    .userId(userId)
                    .roleId(roleId)
                    .build();
            userRoleMapper.insert(userRole);
        }

        auditLogService.logAsync("ROLE_ASSIGN", "USER", userId, 
                Map.of("username", user.getUsername(), "roleIds", roleIds));
    }

    /**
     * Get user by ID
     */
    public UserVO getUserById(String id) {
        SysUser user = getById(id);
        if (user == null || user.getDeleted() == 1) {
            throw new BusinessException(ErrorCode.USER_NOT_FOUND);
        }
        return convertToVO(user);
    }

    /**
     * Query users with pagination
     */
    public Page<UserVO> queryUsers(PageRequest pageRequest, String orgId, String deptId, 
                                   String status, String keyword) {
        Page<SysUser> page = new Page<>(pageRequest.getPage(), pageRequest.getSize());

        LambdaQueryWrapper<SysUser> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(SysUser::getDeleted, 0);

        if (StringUtils.hasText(orgId)) {
            wrapper.eq(SysUser::getOrgId, orgId);
        }
        if (StringUtils.hasText(deptId)) {
            wrapper.eq(SysUser::getDeptId, deptId);
        }
        if (StringUtils.hasText(status)) {
            wrapper.eq(SysUser::getStatus, status);
        }
        if (StringUtils.hasText(keyword)) {
            wrapper.and(w -> w
                    .like(SysUser::getUsername, keyword)
                    .or()
                    .like(SysUser::getRealName, keyword)
                    .or()
                    .like(SysUser::getPhone, keyword)
                    .or()
                    .like(SysUser::getEmail, keyword));
        }

        wrapper.orderByDesc(SysUser::getCreatedAt);

        Page<SysUser> userPage = page(page, wrapper);

        Page<UserVO> voPage = new Page<>(userPage.getCurrent(), userPage.getSize(), userPage.getTotal());
        voPage.setRecords(userPage.getRecords().stream()
                .map(this::convertToVO)
                .collect(Collectors.toList()));

        return voPage;
    }

    /**
     * Delete user (logical delete)
     */
    @Transactional
    public void deleteUser(String id) {
        SysUser user = getById(id);
        if (user == null) {
            throw new BusinessException(ErrorCode.USER_NOT_FOUND);
        }

        user.setDeleted(1);
        updateById(user);

        auditLogService.logAsync("USER_DELETE", "USER", id, 
                Map.of("username", user.getUsername()));
    }

    /**
     * Check if username exists
     */
    public boolean existsByUsername(String username) {
        return count(new LambdaQueryWrapper<SysUser>()
                .eq(SysUser::getUsername, username)
                .eq(SysUser::getDeleted, 0)) > 0;
    }

    /**
     * Get current user from security context
     */
    public SecurityUser getCurrentSecurityUser() {
        return (SecurityUser) SecurityContextHolder.getContext().getAuthentication().getPrincipal();
    }

    /**
     * Convert entity to VO
     */
    private UserVO convertToVO(SysUser user) {
        UserVO vo = UserVO.builder()
                .id(user.getId())
                .username(user.getUsername())
                .realName(user.getRealName())
                .phone(user.getPhone())
                .email(user.getEmail())
                .orgId(user.getOrgId())
                .deptId(user.getDeptId())
                .status(user.getStatus())
                .lastLoginAt(user.getLastLoginAt())
                .createdAt(user.getCreatedAt())
                .build();

        // Get org name
        if (StringUtils.hasText(user.getOrgId())) {
            SysOrg org = orgMapper.selectById(user.getOrgId());
            if (org != null) {
                vo.setOrgName(org.getName());
            }
        }

        // Get dept name
        if (StringUtils.hasText(user.getDeptId())) {
            SysDept dept = deptMapper.selectById(user.getDeptId());
            if (dept != null) {
                vo.setDeptName(dept.getName());
            }
        }

        // Get roles
        List<SysUserRole> userRoles = userRoleMapper.selectList(
                new LambdaQueryWrapper<SysUserRole>().eq(SysUserRole::getUserId, user.getId()));
        
        if (!userRoles.isEmpty()) {
            List<String> roleIds = userRoles.stream()
                    .map(SysUserRole::getRoleId)
                    .collect(Collectors.toList());
            List<SysRole> roles = roleMapper.selectList(
                    new LambdaQueryWrapper<SysRole>().in(SysRole::getId, roleIds));
            vo.setRoles(roles.stream()
                    .map(role -> UserVO.RoleVO.builder()
                            .id(role.getId())
                            .code(role.getCode())
                            .name(role.getName())
                            .build())
                    .collect(Collectors.toList()));
        }

        return vo;
    }
}
