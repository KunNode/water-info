# Unified AI Assessment Situation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make bigscreen and AI command read the same latest persisted AI assessment so risk level, source, summary, and freshness never diverge across pages.

**Architecture:** The platform database remains the authority for AI assessment state. A new frontend Pinia `situation` store loads the latest persisted assessment through REST, uses WebSocket as a refresh accelerator, computes freshness/degradation once, and exposes a canonical risk state consumed by bigscreen and AI command. The backend AI-assessment WebSocket emits a stable `AI_ASSESSMENT_UPDATED` event and ping/pong health events.

**Tech Stack:** Vue 3, Pinia, TypeScript, Axios, Playwright, Spring Boot 3, Java 17, JUnit 5, Mockito, Jackson WebSocket messaging.

---

## Scope Check

This plan covers one subsystem: persisted AI assessment synchronization between platform backend and admin frontend. It deliberately does not create a new `/situation/current` backend aggregate endpoint, change AI model logic, or redesign AI command conversations.

## File Structure

- Modify: `water-info-platform/src/main/java/com/waterinfo/platform/config/AiAssessmentWebSocketHandler.java`
  - Owns AI assessment WebSocket event names, ping/pong behavior, error-message helper, and broadcast payload envelope.
- Test: `water-info-platform/src/test/java/com/waterinfo/platform/config/AiAssessmentWebSocketHandlerTest.java`
  - Verifies ping response and `AI_ASSESSMENT_UPDATED` envelope shape.
- Modify: `water-info-platform/src/main/java/com/waterinfo/platform/module/aiassessment/service/AiAssessmentService.java`
  - Sends WebSocket payload fields aligned with `AiAssessmentVO`.
- Create: `water-info-admin/src/stores/situation.ts`
  - Single frontend fact source for latest persisted AI assessment, canonical risk, freshness, REST recovery, WebSocket refresh, and error state.
- Modify: `water-info-admin/src/views/bigscreen/index.vue`
  - Replaces local alarm-derived AI assessment with `useSituationStore`.
- Modify: `water-info-admin/src/views/ai/command/components/RiskPanel.vue`
  - Reads system situation from `useSituationStore` and keeps conversation risk as a separate process-state display.
- Modify: `water-info-admin/src/views/ai/command/index.vue`
  - Starts the shared situation store and passes conversation risk separately to `RiskPanel`.
- Create: `water-info-admin/tests/e2e/ai-assessment-situation.spec.cjs`
  - Verifies bigscreen and AI command display the same persisted assessment and degrade honestly when no assessment exists.
- Modify: `water-info-admin/playwright.config.cjs`
  - Adds an E2E project that runs the new situation spec without changing the existing smoke project.

## Task 1: Stabilize Backend WebSocket Contract

**Files:**
- Modify: `water-info-platform/src/main/java/com/waterinfo/platform/config/AiAssessmentWebSocketHandler.java`
- Test: `water-info-platform/src/test/java/com/waterinfo/platform/config/AiAssessmentWebSocketHandlerTest.java`

- [ ] **Step 1: Write the failing WebSocket handler test**

Create `water-info-platform/src/test/java/com/waterinfo/platform/config/AiAssessmentWebSocketHandlerTest.java`:

```java
package com.waterinfo.platform.config;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.web.socket.TextMessage;
import org.springframework.web.socket.WebSocketSession;

import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentCaptor.forClass;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class AiAssessmentWebSocketHandlerTest {

    private final ObjectMapper objectMapper = new ObjectMapper();

    @Test
    void repliesPongToPingMessage() throws Exception {
        AiAssessmentWebSocketHandler handler = new AiAssessmentWebSocketHandler();
        WebSocketSession session = mock(WebSocketSession.class);
        when(session.getId()).thenReturn("session-1");
        when(session.isOpen()).thenReturn(true);

        handler.handleTextMessage(session, new TextMessage("ping"));

        var captor = forClass(TextMessage.class);
        verify(session).sendMessage(captor.capture());
        JsonNode payload = objectMapper.readTree(captor.getValue().getPayload());
        assertThat(payload.get("type").asText()).isEqualTo("PONG");
        assertThat(payload.has("timestamp")).isTrue();
    }

    @Test
    void broadcastsAssessmentUpdatedEnvelope() throws Exception {
        AiAssessmentWebSocketHandler handler = new AiAssessmentWebSocketHandler();
        WebSocketSession session = mock(WebSocketSession.class);
        when(session.getId()).thenReturn("session-1");
        when(session.isOpen()).thenReturn(true);
        handler.afterConnectionEstablished(session);

        handler.broadcastAssessment(Map.of(
                "id", "assessment-1",
                "stationId", "station-1",
                "stationName", "翠屏湖心水位站",
                "metricType", "WATER_LEVEL",
                "level", "HIGH",
                "summary", "水位上涨",
                "planExcerpt", "启动巡查",
                "source", "EVENT",
                "assessedAt", "2026-04-29T10:30:00"
        ));

        var captor = forClass(TextMessage.class);
        verify(session).sendMessage(captor.capture());
        JsonNode payload = objectMapper.readTree(captor.getValue().getPayload());
        assertThat(payload.get("type").asText()).isEqualTo("AI_ASSESSMENT_UPDATED");
        assertThat(payload.get("data").get("id").asText()).isEqualTo("assessment-1");
        assertThat(payload.get("data").get("level").asText()).isEqualTo("HIGH");
        assertThat(payload.get("timestamp").asLong()).isGreaterThan(0L);
    }
}
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run:

```bash
cd water-info-platform
./mvnw -q -Dtest=AiAssessmentWebSocketHandlerTest test
```

Expected: FAIL because ping currently returns plain `pong`, and broadcast type is currently `AI_ASSESSMENT`.

- [ ] **Step 3: Implement the WebSocket envelope**

Modify `water-info-platform/src/main/java/com/waterinfo/platform/config/AiAssessmentWebSocketHandler.java` so the constants and methods read:

```java
public static final String TYPE_AI_ASSESSMENT_UPDATED = "AI_ASSESSMENT_UPDATED";
public static final String TYPE_PONG = "PONG";
public static final String TYPE_ERROR = "ERROR";
```

Replace `handleTextMessage` and `broadcastAssessment` with:

```java
@Override
protected void handleTextMessage(WebSocketSession session, TextMessage message) throws Exception {
    if ("ping".equalsIgnoreCase(message.getPayload())) {
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
```

Add this helper inside the class:

```java
private void send(WebSocketSession session, Map<String, Object> message) {
    if (session == null || !session.isOpen()) {
        return;
    }
    try {
        session.sendMessage(new TextMessage(objectMapper.writeValueAsString(message)));
    } catch (IOException e) {
        log.error("Failed to send AI assessment message to session {}: {}", session.getId(), e.getMessage());
    }
}
```

Update the existing `broadcast` loop to call `send(session, message)`:

```java
private void broadcast(Map<String, Object> message) {
    if (sessions.isEmpty()) {
        return;
    }
    sessions.values().forEach(session -> send(session, message));
}
```

- [ ] **Step 4: Run the focused test to verify it passes**

Run:

```bash
cd water-info-platform
./mvnw -q -Dtest=AiAssessmentWebSocketHandlerTest test
```

Expected: PASS, with both WebSocket handler tests green.

- [ ] **Step 5: Commit backend WebSocket contract**

Run:

```bash
git add water-info-platform/src/main/java/com/waterinfo/platform/config/AiAssessmentWebSocketHandler.java \
  water-info-platform/src/test/java/com/waterinfo/platform/config/AiAssessmentWebSocketHandlerTest.java
git commit -m "Align AI assessment WebSocket events with persisted state" \
  -m "The frontend needs one stable refresh signal for persisted AI assessments, so the WebSocket now emits AI_ASSESSMENT_UPDATED and structured PONG health events." \
  -m "Constraint: Preserve the existing /ws/ai-assessments endpoint." \
  -m "Confidence: high" \
  -m "Scope-risk: narrow" \
  -m "Tested: ./mvnw -q -Dtest=AiAssessmentWebSocketHandlerTest test"
```

## Task 2: Add the Frontend Situation Store

**Files:**
- Create: `water-info-admin/src/stores/situation.ts`

- [ ] **Step 1: Create the store with REST authority and WebSocket refresh**

Create `water-info-admin/src/stores/situation.ts`:

```ts
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { getAiAssessments } from '@/api/aiAssessment'
import { useWebSocket } from '@/composables/useWebSocket'
import type { AiAssessment } from '@/types'

export type CanonicalRiskLevel = 'none' | 'low' | 'moderate' | 'high' | 'critical'
export type SituationFreshness = 'fresh' | 'stale' | 'none' | 'offline'
export type SituationConnection = 'idle' | 'connecting' | 'connected' | 'reconnecting' | 'disconnected'

const ASSESSMENT_FRESH_MS = 30 * 60 * 1000
const RISK_LEVELS: CanonicalRiskLevel[] = ['none', 'low', 'moderate', 'high', 'critical']

function normalizeRiskLevel(level?: string | null): CanonicalRiskLevel {
  const normalized = String(level || 'none').trim().toLowerCase()
  return RISK_LEVELS.includes(normalized as CanonicalRiskLevel)
    ? normalized as CanonicalRiskLevel
    : 'none'
}

function isAssessmentFresh(assessment: AiAssessment | null, now = Date.now()) {
  if (!assessment?.assessedAt) return false
  const assessedAt = new Date(assessment.assessedAt).getTime()
  if (!Number.isFinite(assessedAt)) return false
  return now - assessedAt <= ASSESSMENT_FRESH_MS
}

export const useSituationStore = defineStore('situation', () => {
  const latestAssessment = ref<AiAssessment | null>(null)
  const lastSyncedAt = ref<string | null>(null)
  const lastError = ref<string | null>(null)
  const isLoading = ref(false)
  const hasFetchFailure = ref(false)
  const connection = ref<SituationConnection>('idle')
  let streamStarted = false

  const ws = useWebSocket('/ws/ai-assessments')

  const canonicalRiskLevel = computed<CanonicalRiskLevel>(() => {
    return latestAssessment.value && freshness.value !== 'none'
      ? normalizeRiskLevel(latestAssessment.value.level)
      : 'none'
  })

  const freshness = computed<SituationFreshness>(() => {
    if (hasFetchFailure.value) return 'offline'
    if (!latestAssessment.value) return 'none'
    return isAssessmentFresh(latestAssessment.value) ? 'fresh' : 'stale'
  })

  async function refreshLatestAssessment() {
    isLoading.value = true
    try {
      const res = await getAiAssessments({ limit: 1 })
      latestAssessment.value = res.data?.[0] ?? null
      lastSyncedAt.value = new Date().toISOString()
      lastError.value = null
      hasFetchFailure.value = false
    } catch (err: any) {
      lastError.value = err?.message || '获取 AI 研判失败'
      hasFetchFailure.value = true
    } finally {
      isLoading.value = false
    }
  }

  async function ensureFresh() {
    if (!latestAssessment.value || freshness.value !== 'fresh') {
      await refreshLatestAssessment()
    }
  }

  function applyAssessment(payload: unknown) {
    if (!payload || typeof payload !== 'object') return
    const candidate = payload as AiAssessment
    if (!candidate.id || !candidate.assessedAt) return
    latestAssessment.value = candidate
    lastSyncedAt.value = new Date().toISOString()
    lastError.value = null
    hasFetchFailure.value = false
  }

  function handleStreamMessages() {
    const last = ws.messages.value[ws.messages.value.length - 1]
    if (!last || typeof last !== 'object') return

    if (last.type === 'AI_ASSESSMENT_UPDATED') {
      if (last.data?.id && last.data?.assessedAt) {
        applyAssessment(last.data)
      } else {
        refreshLatestAssessment()
      }
    } else if (last.type === 'ERROR') {
      lastError.value = last.message || 'AI 研判推送异常'
    }
  }

  function connectAssessmentStream() {
    if (streamStarted) return
    streamStarted = true
    connection.value = 'connecting'
    ws.connect()

    setInterval(() => {
      connection.value = ws.connected.value ? 'connected' : 'reconnecting'
      handleStreamMessages()
      if (ws.connected.value) {
        ws.send('ping')
      }
    }, 5000)
  }

  function resetForTest() {
    latestAssessment.value = null
    lastSyncedAt.value = null
    lastError.value = null
    isLoading.value = false
    hasFetchFailure.value = false
    connection.value = 'idle'
  }

  return {
    latestAssessment,
    canonicalRiskLevel,
    freshness,
    connection,
    lastSyncedAt,
    lastError,
    isLoading,
    refreshLatestAssessment,
    ensureFresh,
    connectAssessmentStream,
    resetForTest,
  }
})
```

- [ ] **Step 2: Run the frontend typecheck to catch store errors**

Run:

```bash
cd water-info-admin
npm run build
```

Expected before consumer wiring: PASS. This verifies the new store imports and types compile.

- [ ] **Step 3: Commit the store**

Run:

```bash
git add water-info-admin/src/stores/situation.ts
git commit -m "Centralize latest persisted AI assessment state" \
  -m "A shared Pinia store now treats the persisted AI assessment as the frontend authority and uses WebSocket messages only to accelerate refreshes." \
  -m "Constraint: No new frontend dependencies." \
  -m "Confidence: medium" \
  -m "Scope-risk: narrow" \
  -m "Tested: npm run build"
```

## Task 3: Wire Bigscreen to the Situation Store

**Files:**
- Modify: `water-info-admin/src/views/bigscreen/index.vue`

- [ ] **Step 1: Remove the local AI-assessment derivation**

In `water-info-admin/src/views/bigscreen/index.vue`, add imports:

```ts
import { useSituationStore } from '@/stores/situation'
```

Create the store near the router setup:

```ts
const situationStore = useSituationStore()
```

Replace the existing `aiAssessment = computed(() => { ... })` block with:

```ts
const riskDisplayMap: Record<string, { label: string; color: string; trend: string }> = {
  none: { label: 'NORMAL', color: '#2bd99f', trend: '平稳' },
  low: { label: 'LOW', color: '#7aa2ff', trend: '关注' },
  moderate: { label: 'MEDIUM', color: '#ffb547', trend: '上升' },
  high: { label: 'HIGH', color: '#ff5a6a', trend: '上升中' },
  critical: { label: 'CRITICAL', color: '#ff8a96', trend: '急剧上升' },
}

const aiAssessment = computed(() => {
  const assessment = situationStore.latestAssessment
  if (!assessment) return null
  const risk = riskDisplayMap[situationStore.canonicalRiskLevel] ?? riskDisplayMap.none
  return {
    source: assessment.source,
    risk: risk.label,
    color: risk.color,
    trend: risk.trend,
    trigger: assessment.stationName
      ? `来自${assessment.stationName}的持久化研判`
      : '来自最新持久化研判',
    timeLabel: `${assessment.source} · ${formatAlarmAge(assessment.assessedAt)}`,
    summary: assessment.summary,
    planExcerpt: assessment.planExcerpt,
    freshness: situationStore.freshness,
  }
})
```

- [ ] **Step 2: Render degradation labels in the AI Assessment card**

In the AI Assessment template, keep the existing `ai` block and add this line under `<div class="ai__body">{{ aiAssessment.summary }}</div>`:

```vue
<div v-if="aiAssessment.planExcerpt" class="ai__plan">{{ aiAssessment.planExcerpt }}</div>
<div v-if="aiAssessment.freshness !== 'fresh'" class="ai__stale">
  {{ aiAssessment.freshness === 'stale' ? '研判已过期，仅供参考' : '研判同步异常，显示上次结果' }}
</div>
```

Replace the empty state text:

```vue
<div v-else class="empty-tip">
  {{ situationStore.freshness === 'offline' ? '无法获取 AI 研判' : '暂无 AI 研判' }}
</div>
```

Add styles near the AI section:

```scss
.ai__plan {
  margin-top: 8px;
  color: #a9b3c6;
  font-size: 11px;
  line-height: 1.55;
}

.ai__stale {
  margin-top: 8px;
  color: #ffb547;
  font-size: 11px;
  font-family: var(--bs-display-mono);
}
```

- [ ] **Step 3: Start the shared situation sync on mount**

In the existing `onMounted(() => { ... })`, add before `loadData()`:

```ts
situationStore.connectAssessmentStream()
situationStore.ensureFresh()
```

- [ ] **Step 4: Run build**

Run:

```bash
cd water-info-admin
npm run build
```

Expected: PASS. If TypeScript complains about refs, use `situationStore.latestAssessment` directly because Pinia setup-store refs are unwrapped on the store instance.

- [ ] **Step 5: Commit bigscreen wiring**

Run:

```bash
git add water-info-admin/src/views/bigscreen/index.vue
git commit -m "Read bigscreen AI risk from persisted situation state" \
  -m "Bigscreen no longer derives AI risk from alarms; it renders the shared persisted assessment and honest degradation labels." \
  -m "Constraint: Preserve the existing bigscreen layout." \
  -m "Confidence: medium" \
  -m "Scope-risk: moderate" \
  -m "Tested: npm run build"
```

## Task 4: Wire AI Command Risk Panel to the Same Store

**Files:**
- Modify: `water-info-admin/src/views/ai/command/index.vue`
- Modify: `water-info-admin/src/views/ai/command/components/RiskPanel.vue`

- [ ] **Step 1: Pass conversation risk as process state**

In `water-info-admin/src/views/ai/command/index.vue`, change:

```vue
<RiskPanel :riskLevel="store.riskLevel" />
```

to:

```vue
<RiskPanel :conversationRiskLevel="store.riskLevel" />
```

Import and create the situation store:

```ts
import { useSituationStore } from '@/stores/situation'

const situationStore = useSituationStore()
```

Inside `onMounted(async () => { ... })`, after session loading and before `onStructuredEvent`, add:

```ts
situationStore.connectAssessmentStream()
await situationStore.ensureFresh()
```

- [ ] **Step 2: Refactor RiskPanel props and store usage**

In `water-info-admin/src/views/ai/command/components/RiskPanel.vue`, replace imports:

```ts
import { computed, onMounted, ref, watch } from 'vue'
import { getAiAssessments } from '@/api/aiAssessment'
import { useWebSocket } from '@/composables/useWebSocket'
import type { AiAssessment } from '@/types'
```

with:

```ts
import { computed, onMounted, ref } from 'vue'
import { useSituationStore } from '@/stores/situation'
```

Replace props:

```ts
const props = defineProps<{
  riskLevel: string
}>()
```

with:

```ts
const props = defineProps<{
  conversationRiskLevel: string
}>()
```

Add the store:

```ts
const situationStore = useSituationStore()
```

Remove `latestAssessment`, `useWebSocket`, the `watch(scanMessages, ...)`, and the direct `getAiAssessments` call.

Replace computed values with:

```ts
const systemRiskLevel = computed(() => situationStore.canonicalRiskLevel)
const riskInfo = computed(() => riskMap[systemRiskLevel.value] ?? riskMap.none)
const riskColor = computed(() => riskInfo.value.color)
const riskLabel = computed(() => riskInfo.value.label)
const riskSublabel = computed(() => {
  if (situationStore.freshness === 'stale') return '研判已过期'
  if (situationStore.freshness === 'offline') return '同步异常'
  if (situationStore.freshness === 'none') return '暂无 AI 研判'
  return riskInfo.value.sublabel
})
const latestAssessment = computed(() => situationStore.latestAssessment)
const assessmentLevel = computed(() => situationStore.canonicalRiskLevel)
const assessmentColor = computed(() => riskMap[assessmentLevel.value]?.color ?? riskMap.none.color)
const assessmentLabel = computed(() => riskMap[assessmentLevel.value]?.label ?? '研判')
const assessmentTime = computed(() => {
  if (!latestAssessment.value?.assessedAt) return ''
  const d = new Date(latestAssessment.value.assessedAt)
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  const hh = String(d.getHours()).padStart(2, '0')
  const min = String(d.getMinutes()).padStart(2, '0')
  return `${mm}-${dd} ${hh}:${min}`
})
const connectionLabel = computed(() => {
  if (situationStore.freshness === 'offline') return 'offline'
  return situationStore.connection === 'connected' ? 'live' : 'syncing'
})
const degradationLabel = computed(() => {
  if (situationStore.freshness === 'stale') return '研判已过期，仅供参考'
  if (situationStore.freshness === 'offline') return '研判同步异常，显示上次结果'
  if (situationStore.freshness === 'none') return '暂无 AI 研判'
  return ''
})
```

Update `levelActive`:

```ts
function levelActive(level: string) {
  const current = riskOrder.indexOf(systemRiskLevel.value)
  const target = riskOrder.indexOf(level)
  return target <= Math.max(current, 0)
}
```

Update `onMounted`:

```ts
onMounted(async () => {
  situationStore.connectAssessmentStream()
  await situationStore.ensureFresh()
})
```

- [ ] **Step 3: Adjust RiskPanel template labels**

Change the header connection span:

```vue
<span class="mono">{{ connectionLabel }}</span>
```

Inside `.scan-summary`, keep the existing summary and plan blocks, then add:

```vue
<div v-if="degradationLabel" class="degraded">{{ degradationLabel }}</div>
```

Change the empty block:

```vue
<div v-else class="scan-empty">
  <span class="fm-dot" :class="situationStore.freshness === 'offline' ? 'warn' : 'ok'" />
  <span>{{ degradationLabel || '等待 AI 巡检结果' }}</span>
</div>
```

Add CSS:

```scss
.degraded {
  margin-top: 8px;
  color: #ffb547;
  font-size: 11px;
}
```

- [ ] **Step 4: Run build**

Run:

```bash
cd water-info-admin
npm run build
```

Expected: PASS. The AI command page should compile with `conversationRiskLevel` and shared system situation state.

- [ ] **Step 5: Commit AI command wiring**

Run:

```bash
git add water-info-admin/src/views/ai/command/index.vue \
  water-info-admin/src/views/ai/command/components/RiskPanel.vue
git commit -m "Show AI command risk from shared situation state" \
  -m "RiskPanel now separates conversation process risk from the canonical system situation backed by persisted AI assessments." \
  -m "Constraint: Keep SSE conversation flow intact." \
  -m "Confidence: medium" \
  -m "Scope-risk: moderate" \
  -m "Tested: npm run build"
```

## Task 5: Add Consistency E2E Coverage

**Files:**
- Create: `water-info-admin/tests/e2e/ai-assessment-situation.spec.cjs`
- Modify: `water-info-admin/playwright.config.cjs`

- [ ] **Step 1: Add the E2E project**

Modify `water-info-admin/playwright.config.cjs`:

```js
module.exports = {
  testDir: "./tests/e2e",
  timeout: 30_000,
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || "http://localhost:5173",
  },
  projects: [
    {
      name: "smoke",
      testMatch: /smoke\.spec\.cjs$/,
    },
    {
      name: "situation",
      testMatch: /ai-assessment-situation\.spec\.cjs$/,
    },
  ],
}
```

- [ ] **Step 2: Add mocked consistency tests**

Create `water-info-admin/tests/e2e/ai-assessment-situation.spec.cjs`:

```js
const { expect, test } = require("@playwright/test")

const highAssessment = {
  id: "assessment-high-1",
  stationId: "station-1",
  stationName: "翠屏湖心水位站",
  metricType: "WATER_LEVEL",
  level: "HIGH",
  summary: "湖心水位持续上涨，建议加密巡查并准备 III 级响应。",
  planExcerpt: "启动巡查、会商和值守加密。",
  source: "EVENT",
  assessedAt: new Date().toISOString(),
  createdAt: new Date().toISOString(),
}

async function installAuth(page) {
  await page.addInitScript(() => {
    window.localStorage.setItem("water_access_token", "test-token")
  })
}

async function mockCommonApis(page, assessments) {
  await page.route("**/api/v1/ai-assessments**", route => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ code: 200, message: "ok", data: assessments }),
    })
  })
  await page.route("**/api/v1/conversations**", route => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ code: 200, message: "ok", data: [] }),
    })
  })
  await page.route("**/api/v1/stations**", route => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ code: 200, message: "ok", data: { records: [], total: 0 } }),
    })
  })
  await page.route("**/api/v1/sensors**", route => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ code: 200, message: "ok", data: { records: [], total: 0 } }),
    })
  })
  await page.route("**/api/v1/alarms**", route => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ code: 200, message: "ok", data: { records: [], total: 0 } }),
    })
  })
  await page.route("**/api/v1/observations**", route => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ code: 200, message: "ok", data: { records: [], total: 0 } }),
    })
  })
  await page.route("**/api/v1/observations/latest**", route => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ code: 200, message: "ok", data: [] }),
    })
  })
}

test("bigscreen and AI command show the same persisted AI assessment", async ({ page }) => {
  await installAuth(page)
  await mockCommonApis(page, [highAssessment])

  await page.goto("/bigscreen")
  await expect(page.getByText("EVENT")).toBeVisible()
  await expect(page.getByText("HIGH")).toBeVisible()
  await expect(page.getByText("湖心水位持续上涨")).toBeVisible()

  await page.goto("/ai/command")
  await expect(page.getByText("EVENT")).toBeVisible()
  await expect(page.getByText("高风险")).toBeVisible()
  await expect(page.getByText("湖心水位持续上涨")).toBeVisible()
})

test("pages do not invent AI risk when no persisted assessment exists", async ({ page }) => {
  await installAuth(page)
  await mockCommonApis(page, [])

  await page.goto("/bigscreen")
  await expect(page.getByText("暂无 AI 研判")).toBeVisible()

  await page.goto("/ai/command")
  await expect(page.getByText("暂无 AI 研判")).toBeVisible()
})
```

- [ ] **Step 3: Run the situation E2E test to verify behavior**

Start the frontend if it is not already running:

```bash
cd water-info-admin
npm run dev -- --host 0.0.0.0
```

In another shell, run:

```bash
cd water-info-admin
npx playwright test --project=situation
```

Expected: PASS. If the dev server is already on another port, set `PLAYWRIGHT_BASE_URL` to that URL.

- [ ] **Step 4: Run build**

Run:

```bash
cd water-info-admin
npm run build
```

Expected: PASS.

- [ ] **Step 5: Commit E2E coverage**

Run:

```bash
git add water-info-admin/playwright.config.cjs \
  water-info-admin/tests/e2e/ai-assessment-situation.spec.cjs
git commit -m "Verify risk consistency from persisted AI assessments" \
  -m "Playwright now checks that bigscreen and AI command render the same persisted assessment and do not fabricate AI risk when none exists." \
  -m "Constraint: Use existing Playwright setup; no new test dependency." \
  -m "Confidence: medium" \
  -m "Scope-risk: narrow" \
  -m "Tested: npx playwright test --project=situation; npm run build"
```

## Task 6: Final Verification and Cleanup

**Files:**
- Review: all files changed in Tasks 1-5

- [ ] **Step 1: Run backend focused tests**

Run:

```bash
cd water-info-platform
./mvnw -q -Dtest=AiAssessmentWebSocketHandlerTest test
```

Expected: PASS.

- [ ] **Step 2: Run backend compile**

Run:

```bash
cd water-info-platform
./mvnw -q -DskipTests compile
```

Expected: PASS.

- [ ] **Step 3: Run frontend build**

Run:

```bash
cd water-info-admin
npm run build
```

Expected: PASS.

- [ ] **Step 4: Run frontend E2E situation tests**

With the Vite dev server running, run:

```bash
cd water-info-admin
npx playwright test --project=situation
```

Expected: PASS.

- [ ] **Step 5: Check for forbidden risk derivation**

Run:

```bash
rg -n "Placeholder AI assessment|derives a quick read|recentAlarms\\.value\\.sort|AI_ASSESSMENT'" water-info-admin/src/views/bigscreen water-info-admin/src/views/ai/command water-info-admin/src/stores water-info-platform/src/main/java/com/waterinfo/platform/config
```

Expected: no matches for the old placeholder derivation or old `AI_ASSESSMENT` event type.

- [ ] **Step 6: Review git diff**

Run:

```bash
git diff --stat HEAD~5..HEAD
git status --short
```

Expected: only intended files changed, with unrelated pre-existing files left untouched.

- [ ] **Step 7: Commit verification evidence if a report is added**

If no documentation was changed during verification, skip this commit. If a verification note is useful, create `docs/tests/ai-assessment-situation-verification.md` with this content:

```markdown
# AI Assessment Situation Verification

## Commands

- `cd water-info-platform && ./mvnw -q -Dtest=AiAssessmentWebSocketHandlerTest test`
- `cd water-info-platform && ./mvnw -q -DskipTests compile`
- `cd water-info-admin && npm run build`
- `cd water-info-admin && npx playwright test --project=situation`

## Result

All required backend, frontend, and E2E checks passed for the shared persisted AI assessment flow.

## Notes

Bigscreen and AI command now read the same latest persisted AI assessment through the shared situation store.
```

Then commit it:

```bash
git add docs/tests/ai-assessment-situation-verification.md
git commit -m "Record AI assessment situation verification" \
  -m "Verification notes capture backend, frontend, and E2E evidence for the shared persisted AI assessment flow." \
  -m "Confidence: high" \
  -m "Scope-risk: narrow" \
  -m "Tested: ./mvnw -q -Dtest=AiAssessmentWebSocketHandlerTest test; ./mvnw -q -DskipTests compile; npm run build; npx playwright test --project=situation"
```

## Self-Review

Spec coverage:

- Persisted AI assessment as authority: covered by Tasks 2, 3, 4, and 5.
- Frontend unified fact source: covered by Task 2.
- WebSocket as refresh accelerator: covered by Tasks 1 and 2.
- Bigscreen no longer derives AI risk from alarms: covered by Task 3 and Task 6 Step 5.
- AI command reads the same system situation: covered by Task 4.
- Degradation states: covered by Tasks 2, 3, 4, and 5.
- Backend WebSocket contract enhancement: covered by Task 1.
- Verification: covered by Tasks 1, 2, 3, 4, 5, and 6.

Placeholder scan:

- No task relies on unspecified files or unnamed tests.
- No new dependencies are introduced.
- Implementation snippets define the functions and fields used later.

Type consistency:

- `CanonicalRiskLevel`, `SituationFreshness`, and `SituationConnection` are defined in `situation.ts`.
- Store consumers use `canonicalRiskLevel`, `latestAssessment`, `freshness`, `connection`, `ensureFresh`, and `connectAssessmentStream` consistently.
- Backend event type is consistently `AI_ASSESSMENT_UPDATED`.
