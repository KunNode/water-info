package com.waterinfo.platform.user;

import com.waterinfo.platform.common.exception.BusinessException;
import com.waterinfo.platform.common.exception.ErrorCode;
import com.waterinfo.platform.module.user.dto.ChangePasswordRequest;
import com.waterinfo.platform.module.user.dto.CreateUserRequest;
import com.waterinfo.platform.module.user.dto.UpdateUserRequest;
import com.waterinfo.platform.module.user.entity.SysRole;
import com.waterinfo.platform.module.user.entity.SysUser;
import com.waterinfo.platform.module.user.mapper.SysRoleMapper;
import com.waterinfo.platform.module.user.mapper.SysUserMapper;
import com.waterinfo.platform.module.user.service.UserService;
import com.waterinfo.platform.module.user.vo.UserVO;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Unit tests for UserService
 */
@SpringBootTest
@Testcontainers
@ActiveProfiles("test")
class UserServiceTest {

    @Container
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:15-alpine")
            .withDatabaseName("water_info_test")
            .withUsername("test")
            .withPassword("test");

    @DynamicPropertySource
    static void configureProperties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", postgres::getJdbcUrl);
        registry.add("spring.datasource.username", postgres::getUsername);
        registry.add("spring.datasource.password", postgres::getPassword);
    }

    @Autowired
    private UserService userService;

    @Autowired
    private SysUserMapper userMapper;

    @Autowired
    private SysRoleMapper roleMapper;

    @Autowired
    private PasswordEncoder passwordEncoder;

    @BeforeEach
    void setUp() {
        userMapper.delete(null);
        roleMapper.delete(null);
    }

    private SysRole createTestRole(String code, String name) {
        SysRole role = SysRole.builder()
                .code(code)
                .name(name)
                .build();
        roleMapper.insert(role);
        return role;
    }

    @Test
    @DisplayName("Should create a new user successfully")
    void shouldCreateUserSuccessfully() {
        // Given
        CreateUserRequest request = new CreateUserRequest();
        request.setUsername("testuser");
        request.setPassword("password123");
        request.setRealName("Test User");
        request.setEmail("test@example.com");
        request.setPhone("13800138000");

        // When
        UserVO result = userService.createUser(request);

        // Then
        assertNotNull(result.getId());
        assertEquals("testuser", result.getUsername());
        assertEquals("Test User", result.getRealName());
        assertEquals("ACTIVE", result.getStatus());
    }

    @Test
    @DisplayName("Should throw exception when creating user with duplicate username")
    void shouldThrowException_WhenCreatingDuplicateUsername() {
        // Given
        CreateUserRequest request1 = new CreateUserRequest();
        request1.setUsername("duplicate_user");
        request1.setPassword("password123");
        request1.setRealName("First User");
        userService.createUser(request1);

        // When/Then
        CreateUserRequest request2 = new CreateUserRequest();
        request2.setUsername("duplicate_user");
        request2.setPassword("password456");
        request2.setRealName("Second User");

        BusinessException exception = assertThrows(BusinessException.class, () -> {
            userService.createUser(request2);
        });
        assertEquals(ErrorCode.USER_ALREADY_EXISTS.getCode(), exception.getCode());
    }

    @Test
    @DisplayName("Should update user successfully")
    void shouldUpdateUserSuccessfully() {
        // Given
        CreateUserRequest createRequest = new CreateUserRequest();
        createRequest.setUsername("update_user");
        createRequest.setPassword("password123");
        createRequest.setRealName("Original Name");
        UserVO created = userService.createUser(createRequest);

        // When
        UpdateUserRequest updateRequest = new UpdateUserRequest();
        updateRequest.setRealName("Updated Name");
        updateRequest.setEmail("updated@example.com");
        UserVO result = userService.updateUser(created.getId(), updateRequest);

        // Then
        assertEquals("Updated Name", result.getRealName());
        assertEquals("updated@example.com", result.getEmail());
    }

    @Test
    @DisplayName("Should change password successfully")
    void shouldChangePasswordSuccessfully() {
        // Given
        CreateUserRequest createRequest = new CreateUserRequest();
        createRequest.setUsername("password_change_user");
        createRequest.setPassword("oldpassword");
        createRequest.setRealName("Password Change Test");
        UserVO created = userService.createUser(createRequest);

        // When
        ChangePasswordRequest changeRequest = new ChangePasswordRequest();
        changeRequest.setCurrentPassword("oldpassword");
        changeRequest.setNewPassword("newpassword");
        userService.changePassword(created.getId(), changeRequest, false);

        // Then - Verify password was changed
        SysUser user = userMapper.selectById(created.getId());
        assertTrue(passwordEncoder.matches("newpassword", user.getPasswordHash()));
        assertFalse(passwordEncoder.matches("oldpassword", user.getPasswordHash()));
    }

    @Test
    @DisplayName("Should throw exception when current password is incorrect")
    void shouldThrowException_WhenCurrentPasswordIncorrect() {
        // Given
        CreateUserRequest createRequest = new CreateUserRequest();
        createRequest.setUsername("wrong_password_user");
        createRequest.setPassword("correctpassword");
        createRequest.setRealName("Wrong Password Test");
        UserVO created = userService.createUser(createRequest);

        // When/Then
        ChangePasswordRequest changeRequest = new ChangePasswordRequest();
        changeRequest.setCurrentPassword("wrongpassword");
        changeRequest.setNewPassword("newpassword");

        BusinessException exception = assertThrows(BusinessException.class, () -> {
            userService.changePassword(created.getId(), changeRequest, false);
        });
        assertEquals(ErrorCode.USER_PASSWORD_INCORRECT.getCode(), exception.getCode());
    }

    @Test
    @DisplayName("Should allow admin password reset without current password")
    void shouldAllowAdminPasswordReset() {
        // Given
        CreateUserRequest createRequest = new CreateUserRequest();
        createRequest.setUsername("admin_reset_user");
        createRequest.setPassword("oldpassword");
        createRequest.setRealName("Admin Reset Test");
        UserVO created = userService.createUser(createRequest);

        // When - Admin reset (isAdmin = true)
        ChangePasswordRequest changeRequest = new ChangePasswordRequest();
        changeRequest.setNewPassword("adminresetpassword");
        userService.changePassword(created.getId(), changeRequest, true);

        // Then - Verify password was changed
        SysUser user = userMapper.selectById(created.getId());
        assertTrue(passwordEncoder.matches("adminresetpassword", user.getPasswordHash()));
    }

    @Test
    @DisplayName("Should set user roles successfully")
    void shouldSetUserRolesSuccessfully() {
        // Given
        CreateUserRequest createRequest = new CreateUserRequest();
        createRequest.setUsername("role_user");
        createRequest.setPassword("password123");
        createRequest.setRealName("Role Test User");
        UserVO created = userService.createUser(createRequest);

        SysRole role1 = createTestRole("ROLE_TEST_1", "Test Role 1");
        SysRole role2 = createTestRole("ROLE_TEST_2", "Test Role 2");

        // When
        userService.setUserRoles(created.getId(), List.of(role1.getId(), role2.getId()));

        // Then
        UserVO result = userService.getUserById(created.getId());
        assertEquals(2, result.getRoles().size());
    }

    @Test
    @DisplayName("Should throw exception when setting non-existent role")
    void shouldThrowException_WhenSettingNonExistentRole() {
        // Given
        CreateUserRequest createRequest = new CreateUserRequest();
        createRequest.setUsername("invalid_role_user");
        createRequest.setPassword("password123");
        createRequest.setRealName("Invalid Role Test");
        UserVO created = userService.createUser(createRequest);

        // When/Then
        BusinessException exception = assertThrows(BusinessException.class, () -> {
            userService.setUserRoles(created.getId(), List.of("non-existent-role-id"));
        });
        assertEquals(ErrorCode.USER_ROLE_NOT_FOUND.getCode(), exception.getCode());
    }

    @Test
    @DisplayName("Should get user by ID")
    void shouldGetUserById() {
        // Given
        CreateUserRequest createRequest = new CreateUserRequest();
        createRequest.setUsername("get_user");
        createRequest.setPassword("password123");
        createRequest.setRealName("Get Test");
        UserVO created = userService.createUser(createRequest);

        // When
        UserVO result = userService.getUserById(created.getId());

        // Then
        assertEquals(created.getId(), result.getId());
        assertEquals("get_user", result.getUsername());
    }

    @Test
    @DisplayName("Should throw exception when getting non-existent user")
    void shouldThrowException_WhenGettingNonExistentUser() {
        // When/Then
        BusinessException exception = assertThrows(BusinessException.class, () -> {
            userService.getUserById("non-existent-id");
        });
        assertEquals(ErrorCode.USER_NOT_FOUND.getCode(), exception.getCode());
    }

    @Test
    @DisplayName("Should query users with pagination")
    void shouldQueryUsersWithPagination() {
        // Given - Create multiple users
        for (int i = 0; i < 15; i++) {
            CreateUserRequest request = new CreateUserRequest();
            request.setUsername("user_pagination_" + i);
            request.setPassword("password123");
            request.setRealName("User " + i);
            userService.createUser(request);
        }

        // When
        var result = userService.queryUsers(new com.waterinfo.platform.common.api.PageRequest(), null, null, null, null);

        // Then
        assertEquals(10, result.getRecords().size());
        assertEquals(15L, result.getTotal());
    }

    @Test
    @DisplayName("Should query users with keyword filter")
    void shouldQueryUsersWithKeywordFilter() {
        // Given
        CreateUserRequest request1 = new CreateUserRequest();
        request1.setUsername("keyword_test");
        request1.setPassword("password123");
        request1.setRealName("Keyword Real Name");
        userService.createUser(request1);

        CreateUserRequest request2 = new CreateUserRequest();
        request2.setUsername("other_user");
        request2.setPassword("password123");
        request2.setRealName("Other Name");
        userService.createUser(request2);

        // When
        var result = userService.queryUsers(new com.waterinfo.platform.common.api.PageRequest(), null, null, null, "keyword");

        // Then
        assertEquals(1, result.getRecords().size());
        assertEquals("keyword_test", result.getRecords().get(0).getUsername());
    }

    @Test
    @DisplayName("Should delete user (logical delete)")
    void shouldDeleteUser() {
        // Given
        CreateUserRequest request = new CreateUserRequest();
        request.setUsername("delete_user");
        request.setPassword("password123");
        request.setRealName("Delete Test");
        UserVO created = userService.createUser(request);

        // When
        userService.deleteUser(created.getId());

        // Then - Should throw exception when trying to get deleted user
        BusinessException exception = assertThrows(BusinessException.class, () -> {
            userService.getUserById(created.getId());
        });
        assertEquals(ErrorCode.USER_NOT_FOUND.getCode(), exception.getCode());
    }

    @Test
    @DisplayName("Should check if username exists")
    void shouldCheckIfUsernameExists() {
        // Given
        CreateUserRequest request = new CreateUserRequest();
        request.setUsername("exists_check_user");
        request.setPassword("password123");
        request.setRealName("Exists Check");
        userService.createUser(request);

        // When
        boolean exists = userService.existsByUsername("exists_check_user");
        boolean notExists = userService.existsByUsername("non_existent_user");

        // Then
        assertTrue(exists);
        assertFalse(notExists);
    }
}
