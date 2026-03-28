package com.waterinfo.platform.module.auth.service;

import com.waterinfo.platform.common.exception.BusinessException;
import com.waterinfo.platform.common.exception.ErrorCode;
import com.waterinfo.platform.module.auth.dto.LoginRequest;
import com.waterinfo.platform.module.auth.dto.LoginResponse;
import com.waterinfo.platform.module.user.entity.SysUser;
import com.waterinfo.platform.module.user.mapper.SysUserMapper;
import com.waterinfo.platform.security.JwtTokenProvider;
import com.waterinfo.platform.security.SecurityUser;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.BadCredentialsException;
import org.springframework.security.authentication.DisabledException;
import org.springframework.security.authentication.LockedException;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;

/**
 * Authentication service
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AuthService {

    private final AuthenticationManager authenticationManager;
    private final JwtTokenProvider tokenProvider;
    private final SysUserMapper userMapper;

    /**
     * Login and generate JWT token
     */
    @Transactional
    public LoginResponse login(LoginRequest request) {
        try {
            Authentication authentication = authenticationManager.authenticate(
                    new UsernamePasswordAuthenticationToken(request.getUsername(), request.getPassword())
            );

            SecurityContextHolder.getContext().setAuthentication(authentication);
            SecurityUser userDetails = (SecurityUser) authentication.getPrincipal();

            // Generate tokens
            String accessToken = tokenProvider.generateToken(userDetails);
            String refreshToken = tokenProvider.generateRefreshToken(userDetails);

            // Update last login time
            SysUser user = userMapper.selectById(userDetails.getId());
            if (user != null) {
                user.setLastLoginAt(LocalDateTime.now());
                userMapper.updateById(user);
            }

            return LoginResponse.builder()
                    .accessToken(accessToken)
                    .refreshToken(refreshToken)
                    .tokenType("Bearer")
                    .expiresIn(86400L) // 24 hours
                    .user(LoginResponse.UserInfo.builder()
                            .id(userDetails.getId())
                            .username(userDetails.getUsername())
                            .realName(userDetails.getRealName())
                            .orgId(userDetails.getOrgId())
                            .deptId(userDetails.getDeptId())
                            .roles(userDetails.getRoles())
                            .build())
                    .build();

        } catch (BadCredentialsException e) {
            log.warn("Login failed for user {}: invalid credentials", request.getUsername());
            throw new BusinessException(ErrorCode.AUTH_INVALID_CREDENTIALS);
        } catch (DisabledException e) {
            log.warn("Login failed for user {}: account disabled", request.getUsername());
            throw new BusinessException(ErrorCode.AUTH_USER_DISABLED);
        } catch (LockedException e) {
            log.warn("Login failed for user {}: account locked", request.getUsername());
            throw new BusinessException(ErrorCode.AUTH_USER_LOCKED);
        }
    }

    /**
     * Get current user info
     */
    public LoginResponse.UserInfo getCurrentUser() {
        Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
        if (authentication == null || !(authentication.getPrincipal() instanceof SecurityUser)) {
            throw new BusinessException(ErrorCode.UNAUTHORIZED);
        }

        SecurityUser userDetails = (SecurityUser) authentication.getPrincipal();
        return LoginResponse.UserInfo.builder()
                .id(userDetails.getId())
                .username(userDetails.getUsername())
                .realName(userDetails.getRealName())
                .orgId(userDetails.getOrgId())
                .deptId(userDetails.getDeptId())
                .roles(userDetails.getRoles())
                .build();
    }
}
