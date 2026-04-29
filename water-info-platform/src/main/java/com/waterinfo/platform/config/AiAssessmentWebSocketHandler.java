package com.waterinfo.platform.config;

import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.socket.CloseStatus;
import org.springframework.web.socket.TextMessage;
import org.springframework.web.socket.WebSocketSession;
import org.springframework.web.socket.handler.TextWebSocketHandler;

import java.io.IOException;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

@Slf4j
public class AiAssessmentWebSocketHandler extends TextWebSocketHandler {

    public static final String TYPE_AI_ASSESSMENT_UPDATED = "AI_ASSESSMENT_UPDATED";
    public static final String TYPE_PONG = "PONG";
    public static final String TYPE_ERROR = "ERROR";

    private final Map<String, WebSocketSession> sessions = new ConcurrentHashMap<>();
    private final ObjectMapper objectMapper = new ObjectMapper();

    @Override
    public void afterConnectionEstablished(WebSocketSession session) {
        sessions.put(session.getId(), session);
        log.info("AI assessment WebSocket connected: sessionId={}, total={}", session.getId(), sessions.size());
    }

    @Override
    public void afterConnectionClosed(WebSocketSession session, CloseStatus status) {
        sessions.remove(session.getId());
        log.info("AI assessment WebSocket disconnected: sessionId={}, total={}", session.getId(), sessions.size());
    }

    @Override
    protected void handleTextMessage(WebSocketSession session, TextMessage message) throws Exception {
        if ("ping".equals(message.getPayload())) {
            send(session, Map.of(
                    "type", TYPE_PONG,
                    "timestamp", System.currentTimeMillis()
            ));
        }
    }

    public void broadcastAssessment(Map<String, Object> assessmentData) {
        broadcast(Map.of(
                "type", TYPE_AI_ASSESSMENT_UPDATED,
                "data", assessmentData,
                "timestamp", System.currentTimeMillis()
        ));
    }

    public void broadcastError(String message) {
        broadcast(Map.of(
                "type", TYPE_ERROR,
                "message", message,
                "timestamp", System.currentTimeMillis()
        ));
    }

    private void broadcast(Map<String, Object> message) {
        if (sessions.isEmpty()) {
            return;
        }
        sessions.values().forEach(session -> send(session, message));
    }

    private void send(WebSocketSession session, Map<String, Object> message) {
        if (!session.isOpen()) {
            return;
        }
        try {
            String json = objectMapper.writeValueAsString(message);
            session.sendMessage(new TextMessage(json));
        } catch (IOException e) {
            log.error("Failed to send AI assessment message to session {}: {}", session.getId(), e.getMessage());
        }
    }
}
