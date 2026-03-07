package com.waterinfo.platform.config;

import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import org.springframework.web.socket.CloseStatus;
import org.springframework.web.socket.TextMessage;
import org.springframework.web.socket.WebSocketSession;
import org.springframework.web.socket.handler.TextWebSocketHandler;

import java.io.IOException;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * WebSocket handler for real-time alarm notifications
 */
@Slf4j
@Component
public class AlarmWebSocketHandler extends TextWebSocketHandler {

    private final Map<String, WebSocketSession> sessions = new ConcurrentHashMap<>();
    private final ObjectMapper objectMapper = new ObjectMapper();

    public static final String TYPE_ALARM_NEW = "ALARM_NEW";
    public static final String TYPE_ALARM_UPDATE = "ALARM_UPDATE";
    public static final String TYPE_ALARM_DELETE = "ALARM_DELETE";
    public static final String TYPE_HEARTBEAT = "HEARTBEAT";

    @Override
    public void afterConnectionEstablished(WebSocketSession session) throws Exception {
        sessions.put(session.getId(), session);
        log.info("WebSocket connected: sessionId={}, total={}", session.getId(), sessions.size());
    }

    @Override
    public void afterConnectionClosed(WebSocketSession session, CloseStatus status) throws Exception {
        sessions.remove(session.getId());
        log.info("WebSocket disconnected: sessionId={}, total={}", session.getId(), sessions.size());
    }

    @Override
    protected void handleTextMessage(WebSocketSession session, TextMessage message) throws Exception {
        String payload = message.getPayload();
        log.debug("Received message from {}: {}", session.getId(), payload);

        // Handle heartbeat
        if ("ping".equals(payload)) {
            session.sendMessage(new TextMessage("pong"));
        }
    }

    @Override
    public void handleTransportError(WebSocketSession session, Throwable exception) throws Exception {
        log.error("WebSocket transport error: sessionId={}, error={}", session.getId(), exception.getMessage());
        sessions.remove(session.getId());
    }

    /**
     * Broadcast alarm to all connected clients
     */
    public void broadcastAlarm(Map<String, Object> alarmData) {
        Map<String, Object> message = Map.of(
                "type", TYPE_ALARM_NEW,
                "data", alarmData,
                "timestamp", System.currentTimeMillis()
        );
        broadcast(message);
    }

    /**
     * Broadcast alarm update to all connected clients
     */
    public void broadcastAlarmUpdate(Map<String, Object> alarmData) {
        Map<String, Object> message = Map.of(
                "type", TYPE_ALARM_UPDATE,
                "data", alarmData,
                "timestamp", System.currentTimeMillis()
        );
        broadcast(message);
    }

    /**
     * Broadcast alarm deletion to all connected clients
     */
    public void broadcastAlarmDelete(String alarmId) {
        Map<String, Object> message = Map.of(
                "type", TYPE_ALARM_DELETE,
                "data", Map.of("id", alarmId),
                "timestamp", System.currentTimeMillis()
        );
        broadcast(message);
    }

    /**
     * Broadcast message to all connected sessions
     */
    private void broadcast(Map<String, Object> message) {
        if (sessions.isEmpty()) {
            return;
        }

        String json;
        try {
            json = objectMapper.writeValueAsString(message);
        } catch (IOException e) {
            log.error("Failed to serialize message: {}", e.getMessage());
            return;
        }

        TextMessage textMessage = new TextMessage(json);
        for (WebSocketSession session : sessions.values()) {
            try {
                if (session.isOpen()) {
                    session.sendMessage(textMessage);
                }
            } catch (IOException e) {
                log.error("Failed to send message to session {}: {}", session.getId(), e.getMessage());
            }
        }
    }

    /**
     * Get connected session count
     */
    public int getConnectedCount() {
        return sessions.size();
    }
}
