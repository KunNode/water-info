package com.waterinfo.platform.module.alarm.listener;

import com.waterinfo.platform.module.alarm.client.WaterInfoAiClient;
import com.waterinfo.platform.module.alarm.event.RiskEscalatedEvent;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Component;
import org.springframework.transaction.event.TransactionalEventListener;

@Slf4j
@Component
@RequiredArgsConstructor
public class RiskEscalatedEventListener {

    private final WaterInfoAiClient aiClient;

    @Async
    @TransactionalEventListener(fallbackExecution = true)
    public void onRiskEscalated(RiskEscalatedEvent event) {
        log.info("Triggering AI risk scan: station={}, metric={}, level={}",
                event.stationId(), event.metricType(), event.level());
        aiClient.triggerRiskScan(event.stationId(), event.metricType(), event.level());
    }
}
