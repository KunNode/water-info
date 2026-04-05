package com.waterinfo.platform.module.ai.context;

import com.waterinfo.platform.security.SecurityUser;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.ReactiveSecurityContextHolder;
import org.springframework.security.core.context.SecurityContext;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Mono;

/**
 * Helper to extract current user info for AI service requests.
 * The user identity is forwarded via X-User-Id and X-Username headers.
 */
@Slf4j
@Component
public class AiUserContext {

    public static final String HEADER_USER_ID = "X-User-Id";
    public static final String HEADER_USERNAME = "X-Username";

    /**
     * Get current user info from reactive security context.
     */
    public Mono<UserInfo> getCurrentUser() {
        return ReactiveSecurityContextHolder.getContext()
                .map(SecurityContext::getAuthentication)
                .filter(auth -> auth != null && auth.isAuthenticated())
                .map(this::extractUserInfo)
                .defaultIfEmpty(UserInfo.anonymous());
    }

    private UserInfo extractUserInfo(Authentication auth) {
        Object principal = auth.getPrincipal();
        if (principal instanceof SecurityUser securityUser) {
            return new UserInfo(
                    securityUser.getId(),
                    securityUser.getUsername()
            );
        }
        // Fallback: use principal name
        String name = auth.getName();
        return new UserInfo(name, name);
    }

    /**
     * Immutable user info record for forwarding to AI service.
     */
    public record UserInfo(String userId, String username) {
        public static UserInfo anonymous() {
            return new UserInfo("", "");
        }

        public boolean isAuthenticated() {
            return userId != null && !userId.isBlank();
        }
    }
}
