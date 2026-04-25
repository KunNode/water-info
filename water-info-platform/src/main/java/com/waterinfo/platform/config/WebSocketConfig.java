package com.waterinfo.platform.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.socket.config.annotation.EnableWebSocket;
import org.springframework.web.socket.config.annotation.WebSocketConfigurer;
import org.springframework.web.socket.config.annotation.WebSocketHandlerRegistry;
import org.springframework.web.socket.server.standard.ServerEndpointExporter;

/**
 * WebSocket configuration
 */
@Configuration
@EnableWebSocket
public class WebSocketConfig implements WebSocketConfigurer {

    public static final String ALARM_WS_ENDPOINT = "/ws/alarms";
    public static final String AI_ASSESSMENT_WS_ENDPOINT = "/ws/ai-assessments";

    @Bean
    public ServerEndpointExporter serverEndpointExporter() {
        return new ServerEndpointExporter();
    }

    @Override
    public void registerWebSocketHandlers(WebSocketHandlerRegistry registry) {
        registry.addHandler(alarmWebSocketHandler(), ALARM_WS_ENDPOINT)
                .setAllowedOrigins("*");
        registry.addHandler(aiAssessmentWebSocketHandler(), AI_ASSESSMENT_WS_ENDPOINT)
                .setAllowedOrigins("*");
    }

    @Bean
    public AlarmWebSocketHandler alarmWebSocketHandler() {
        return new AlarmWebSocketHandler();
    }

    @Bean
    public AiAssessmentWebSocketHandler aiAssessmentWebSocketHandler() {
        return new AiAssessmentWebSocketHandler();
    }
}
