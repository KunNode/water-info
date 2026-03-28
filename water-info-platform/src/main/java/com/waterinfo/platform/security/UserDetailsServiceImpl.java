package com.waterinfo.platform.security;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.waterinfo.platform.module.user.entity.SysRole;
import com.waterinfo.platform.module.user.entity.SysUser;
import com.waterinfo.platform.module.user.entity.SysUserRole;
import com.waterinfo.platform.module.user.mapper.SysRoleMapper;
import com.waterinfo.platform.module.user.mapper.SysUserMapper;
import com.waterinfo.platform.module.user.mapper.SysUserRoleMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.core.userdetails.UsernameNotFoundException;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.stream.Collectors;

/**
 * User details service implementation for Spring Security
 */
@Service
@RequiredArgsConstructor
public class UserDetailsServiceImpl implements UserDetailsService {

    private final SysUserMapper userMapper;
    private final SysUserRoleMapper userRoleMapper;
    private final SysRoleMapper roleMapper;

    @Override
    public UserDetails loadUserByUsername(String username) throws UsernameNotFoundException {
        // Find user by username
        SysUser user = userMapper.selectOne(
                new LambdaQueryWrapper<SysUser>()
                        .eq(SysUser::getUsername, username)
                        .eq(SysUser::getDeleted, 0)
        );

        if (user == null) {
            throw new UsernameNotFoundException("User not found: " + username);
        }

        // Get user roles
        List<SysUserRole> userRoles = userRoleMapper.selectList(
                new LambdaQueryWrapper<SysUserRole>()
                        .eq(SysUserRole::getUserId, user.getId())
        );

        List<String> roleIds = userRoles.stream()
                .map(SysUserRole::getRoleId)
                .collect(Collectors.toList());

        List<String> roleCodes;
        if (!roleIds.isEmpty()) {
            List<SysRole> roles = roleMapper.selectList(
                    new LambdaQueryWrapper<SysRole>()
                            .in(SysRole::getId, roleIds)
            );
            roleCodes = roles.stream()
                    .map(SysRole::getCode)
                    .collect(Collectors.toList());
        } else {
            roleCodes = List.of();
        }

        return SecurityUser.builder()
                .id(user.getId())
                .username(user.getUsername())
                .password(user.getPasswordHash())
                .realName(user.getRealName())
                .orgId(user.getOrgId())
                .deptId(user.getDeptId())
                .roles(roleCodes)
                .enabled("ACTIVE".equals(user.getStatus()))
                .accountNonLocked(!"LOCKED".equals(user.getStatus()))
                .build();
    }
}
