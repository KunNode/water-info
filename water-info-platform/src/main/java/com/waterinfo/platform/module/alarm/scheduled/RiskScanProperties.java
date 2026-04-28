package com.waterinfo.platform.module.alarm.scheduled;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

@Data
@Component
@ConfigurationProperties(prefix = "water-info.risk-scan")
public class RiskScanProperties {

    private Lightweight lightweight = new Lightweight();

    private Ai ai = new Ai();

    @Data
    public static class Lightweight {
        private boolean enabled = true;
        private long intervalMs = 90_000L;
        private long windowSeconds = 300L;
    }

    @Data
    public static class Ai {
        private String baseUrl = "http://water-info-ai:8100";
        private String serviceToken = "";
        private long timeoutMs = 5_000L;
    }
}
