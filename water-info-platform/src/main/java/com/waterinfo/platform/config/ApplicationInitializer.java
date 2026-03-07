package com.waterinfo.platform.config;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.waterinfo.platform.module.user.entity.SysRole;
import com.waterinfo.platform.module.user.entity.SysUser;
import com.waterinfo.platform.module.user.entity.SysUserRole;
import com.waterinfo.platform.module.user.mapper.SysRoleMapper;
import com.waterinfo.platform.module.user.mapper.SysUserMapper;
import com.waterinfo.platform.module.user.mapper.SysUserRoleMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;

/**
 * Application initializer for creating default admin user on startup
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class ApplicationInitializer implements ApplicationRunner {

    private final SysUserMapper userMapper;
    private final SysRoleMapper roleMapper;
    private final SysUserRoleMapper userRoleMapper;
    private final PasswordEncoder passwordEncoder;

    @Value("${app.admin.username:admin}")
    private String adminUsername;

    @Value("${app.admin.password:Admin@123456}")
    private String adminPassword;

    @Value("${app.admin.real-name:System Administrator}")
    private String adminRealName;

    @Override
    public void run(ApplicationArguments args) {
        initializeDefaultAdmin();
    }

    private void initializeDefaultAdmin() {
        // Check if admin user exists
        SysUser existingAdmin = userMapper.selectOne(
                new LambdaQueryWrapper<SysUser>()
                        .eq(SysUser::getUsername, adminUsername)
                        .eq(SysUser::getDeleted, 0));

        if (existingAdmin != null) {
            log.info("Admin user '{}' already exists, skipping initialization", adminUsername);
            return;
        }

        // Get ADMIN role
        SysRole adminRole = roleMapper.selectOne(
                new LambdaQueryWrapper<SysRole>().eq(SysRole::getCode, "ADMIN"));

        if (adminRole == null) {
            log.error("ADMIN role not found in database. Please ensure database migration completed successfully.");
            return;
        }

        // Create admin user
        SysUser admin = SysUser.builder()
                .username(adminUsername)
                .passwordHash(passwordEncoder.encode(adminPassword))
                .realName(adminRealName)
                .status("ACTIVE")
                .passwordUpdatedAt(LocalDateTime.now())
                .deleted(0)
                .build();

        userMapper.insert(admin);
        log.info("Created default admin user: {}", adminUsername);

        // Assign ADMIN role
        SysUserRole userRole = SysUserRole.builder()
                .userId(admin.getId())
                .roleId(adminRole.getId())
                .build();
        userRoleMapper.insert(userRole);
        log.info("Assigned ADMIN role to user: {}", adminUsername);

        log.warn("===============================================");
        log.warn("DEFAULT ADMIN USER CREATED!");
        log.warn("Username: {}", adminUsername);
        log.warn("Password: [configured in application.yml]");
        log.warn("PLEASE CHANGE THE PASSWORD AFTER FIRST LOGIN!");
        log.warn("===============================================");
    }
}
