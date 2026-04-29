package com.waterinfo.platform.config;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.web.socket.TextMessage;
import org.springframework.web.socket.WebSocketSession;

import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class AiAssessmentWebSocketHandlerTest {

    private final ObjectMapper objectMapper = new ObjectMapper();

    @Mock
    private WebSocketSession session;

    @Test
    void repliesPongToPingMessageIgnoringCase() throws Exception {
        AiAssessmentWebSocketHandler handler = new AiAssessmentWebSocketHandler();
        when(session.isOpen()).thenReturn(true);

        handler.handleTextMessage(session, new TextMessage("PiNg"));

        ArgumentCaptor<TextMessage> messageCaptor = ArgumentCaptor.forClass(TextMessage.class);
        verify(session).sendMessage(messageCaptor.capture());

        JsonNode response = objectMapper.readTree(messageCaptor.getValue().getPayload());
        assertThat(response.path("type").asText()).isEqualTo("PONG");
        assertThat(response.has("timestamp")).isTrue();
    }

    @Test
    void broadcastsAssessmentUpdatedAndLegacyEnvelopes() throws Exception {
        AiAssessmentWebSocketHandler handler = new AiAssessmentWebSocketHandler();
        when(session.getId()).thenReturn("session-1");
        when(session.isOpen()).thenReturn(true);

        handler.afterConnectionEstablished(session);
        handler.broadcastAssessment(Map.of(
                "id", "assessment-1",
                "level", "HIGH"
        ));

        ArgumentCaptor<TextMessage> messageCaptor = ArgumentCaptor.forClass(TextMessage.class);
        verify(session, times(2)).sendMessage(messageCaptor.capture());

        assertThat(messageCaptor.getAllValues()).hasSize(2);

        JsonNode updatedResponse = objectMapper.readTree(messageCaptor.getAllValues().get(0).getPayload());
        assertThat(updatedResponse.path("type").asText()).isEqualTo("AI_ASSESSMENT_UPDATED");
        assertThat(updatedResponse.path("data").path("id").asText()).isEqualTo("assessment-1");
        assertThat(updatedResponse.path("data").path("level").asText()).isEqualTo("HIGH");
        assertThat(updatedResponse.path("timestamp").asLong()).isGreaterThan(0L);

        JsonNode legacyResponse = objectMapper.readTree(messageCaptor.getAllValues().get(1).getPayload());
        assertThat(legacyResponse.path("type").asText()).isEqualTo("AI_ASSESSMENT");
        assertThat(legacyResponse.path("data").path("id").asText()).isEqualTo("assessment-1");
        assertThat(legacyResponse.path("data").path("level").asText()).isEqualTo("HIGH");
        assertThat(legacyResponse.path("timestamp").asLong()).isGreaterThan(0L);
    }
}
