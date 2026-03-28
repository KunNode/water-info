package com.waterinfo.platform.module.user.vo;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.List;

/**
 * User view object
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class UserVO {

    private String id;
    private String username;
    private String realName;
    private String phone;
    private String email;
    private String orgId;
    private String orgName;
    private String deptId;
    private String deptName;
    private String status;
    private LocalDateTime lastLoginAt;
    private LocalDateTime createdAt;
    private List<RoleVO> roles;

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class RoleVO {
        private String id;
        private String code;
        private String name;
    }
}
