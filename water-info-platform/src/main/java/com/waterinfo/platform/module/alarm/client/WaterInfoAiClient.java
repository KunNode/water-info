package com.waterinfo.platform.module.alarm.client;

import com.waterinfo.platform.module.alarm.scheduled.RiskScanProperties;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.util.retry.Retry;

import java.time.Duration;
import java.util.Map;

@Slf4j
@Component
@RequiredArgsConstructor
public class WaterInfoAiClient {

    private final WebClient.Builder webClientBuilder;
    private final RiskScanProperties properties;

    public void triggerRiskScan(String stationId, String metricType, String level) {
        RiskScanProperties.Ai ai = properties.getAi();
        WebClient.RequestBodySpec request = webClientBuilder
                .baseUrl(ai.getBaseUrl())
                .build()
                .post()
                .uri("/api/v1/flood/risk-scan/trigger")
                .contentType(MediaType.APPLICATION_JSON);

        if (StringUtils.hasText(ai.getServiceToken())) {
            request.header(HttpHeaders.AUTHORIZATION, "Bearer " + ai.getServiceToken());
        }

        request.bodyValue(Map.of(
                        "stationId", stationId,
                        "metricType", metricType,
                        "level", level
                ))
                .retrieve()
                .bodyToMono(String.class)
                .timeout(Duration.ofMillis(ai.getTimeoutMs()))
                .retryWhen(Retry.fixedDelay(2, Duration.ofMillis(300)))
                .doOnError(ex -> log.warn("AI risk scan trigger failed: station={}, metric={}, level={}, error={}",
                        stationId, metricType, level, ex.getMessage()))
                .subscribe();
    }
}
