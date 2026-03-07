package com.waterinfo.platform.module.ai.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

/**
 * AI service configuration properties
 */
@Data
@Component
@ConfigurationProperties(prefix = "ai.service")
public class AiServiceProperties {

    private String url = "http://localhost:8100";
    private int timeoutSeconds = 180;
    private int connectTimeoutSeconds = 10;
}
