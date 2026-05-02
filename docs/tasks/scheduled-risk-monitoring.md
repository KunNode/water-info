---
title: 定时险情监测 — 轻量层兜底 + AI 层增强
status: proposed
owner: TBD
created: 2026-04-25
---

## 1. 目标

在现有「被动告警 / 用户主动问询 AI」的基础上，新增**两层定时主动巡检**，把险情发现的延迟从分钟级（依赖人工触发）压到秒级–分钟级，并在多因素演化态势下输出研判结论与初步处置建议。

成功标准：

- 任一已配置 `threshold-rule` 命中后，**≤2 分钟**生成 `OPEN` 状态告警并通过 `/ws/alarms` 推送到前端。
- 高等级告警（`level ∈ {high, critical}`）出现后，**≤5 分钟**完成一次 AI 综合研判并把 plan + risk 报告写回平台。
- 不允许重复刷屏：同站同指标同级别 30 分钟内只产生一条 `OPEN` 告警；AI 研判默认 15 分钟一次，可被高等级告警事件提前触发。

非目标：

- 不改造 `threshold-rule` 模型本身。
- 不替换现有 WebSocket 推送链路。
- AI 层不做长周期趋势预测（≥小时级），只做"当前态势 + 短期处置"研判。

---

## 2. 总体方案

```
                ┌──────────────────────────── water-info-platform (Spring) ─────────────────────────────┐
                │                                                                                       │
   PG/observ →  │  ScheduledRiskScanJob (@Scheduled, 1–2 min)                                          │
                │     │                                                                                 │
                │     ├── ThresholdRuleService.findEnabledRules(...)                                   │
                │     ├── ObservationMapper.findLatestPerStation(window)                               │
                │     ├── 命中规则 → AlarmService.createOrUpdateAlarm(...)  →  AlarmWebSocketHandler   │
                │     └── 命中 high/critical → 发布 RiskEscalatedEvent (Spring ApplicationEvent)        │
                │                                                                                       │
                └──────────────────────┬────────────────────────────────────────────────────────────────┘
                                       │ HTTP POST /api/v1/flood/risk-scan/trigger  (内部接口)
                                       ▼
                ┌──────────────────── water-info-ai (FastAPI + APScheduler) ────────────────────────────┐
                │                                                                                       │
                │  RiskScanScheduler                                                                    │
                │     ├── 周期任务 (默认 15 min): 全量站点采样 → RiskAssessor → 生成研判报告              │
                │     └── 事件触发  (来自平台 RiskEscalated): 仅针对升级站点 → RiskAssessor + PlanGen     │
                │                                                                                       │
                │  产出 → platform_client.upsert_ai_assessment(...)  写回平台                            │
                │       → 通过现有 SSE/WebSocket 通道推前端"AI 研判"卡片                                 │
                └───────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. 轻量层（Spring `@Scheduled`）

### 3.1 新增文件

- `water-info-platform/src/main/java/com/waterinfo/platform/module/alarm/scheduled/ScheduledRiskScanJob.java`
- `water-info-platform/src/main/java/com/waterinfo/platform/module/alarm/event/RiskEscalatedEvent.java`
- `water-info-platform/src/main/java/com/waterinfo/platform/module/alarm/scheduled/RiskScanProperties.java` (`@ConfigurationProperties("water-info.risk-scan")`)
- 测试：`src/test/java/.../alarm/scheduled/ScheduledRiskScanJobTest.java`（Testcontainers + 真实 PG）

### 3.2 修改文件

- `water-info-platform/.../WaterInfoPlatformApplication.java`：加 `@EnableScheduling`（若未开启）。
- `application.yml` / `application-dev.yml` / `application-prod.yml`：新增配置块（见 §6）。
- `AlarmService.createOrUpdateAlarm(...)`：保持现有签名；如需返回"是否为新告警 / 是否升级"语义，新增 `AlarmCreateResult` 出参（不破坏旧调用）。

### 3.3 任务逻辑

```
@Scheduled(fixedDelayString = "${water-info.risk-scan.lightweight.interval-ms:90000}")
public void scan():
    if (!props.lightweight.enabled) return
    rules = thresholdRuleService.findEnabledRules(null, null)
    rulesByStation = group by stationId,metricType
    latest = observationMapper.findLatestPerStation(rulesByStation.keys, window=props.window)
    for (station, metric, obs) in latest:
        rule = pickHighestSeverityHit(obs, rulesByStation[(station,metric)])
        if rule == null: continue
        result = alarmService.createOrUpdateAlarm(station, metric, rule.level, obs.value, rule.id, sourceTag="SCHEDULED")
        if result.isNewOrEscalated && rule.level in {HIGH, CRITICAL}:
            publisher.publishEvent(new RiskEscalatedEvent(station, metric, rule.level, obs.value))
```

要点：

- **去重**：复用 `AlarmService` 现有"同站同指标同级别 OPEN 告警合并"语义；不在 Job 里再做一份。如果当前 service 没有该语义，先在 service 层加 unique 约束（`alarm` 表 `(station_id, metric_type, level, status)` 部分唯一索引 where `status='OPEN'`），通过新增 Flyway `V6__alarm_open_unique_idx.sql` 实现。
- **窗口**：`window` 默认 5 分钟，避免漏掉刚到的批量上传数据。
- **数据量**：`findLatestPerStation` 必须用 SQL `DISTINCT ON (station_id, metric_type)` 或 lateral join，**禁止**全表扫 observation；走 `V5__performance_indexes.sql` 已有的 `(station_id, metric_type, observed_at desc)` 索引。
- **失败隔离**：单站异常不阻断整轮；任务总耗时 > `interval` 时打 WARN，便于发现负载问题。
- **可观测**：Micrometer 计数器 `risk_scan_runs_total`、`risk_scan_alarms_emitted_total{level}`、`risk_scan_duration_seconds`。

### 3.4 事件转发到 AI 层

- `RiskEscalatedEvent` 由独立 `@Async` 监听器消费 → 调 `WaterInfoAiClient.triggerRiskScan(stationId, metricType, level)`。
- `WaterInfoAiClient`：新增 Feign/RestClient bean，`base-url` 走 `water-info.ai.base-url` 配置；带 5s 超时 + Resilience4j retry(3) + circuit breaker；失败仅记日志，**不**回滚告警。

---

## 4. AI 增强层（`water-info-ai` + APScheduler）

### 4.1 新增文件

- `water-info-ai/app/services/risk_scan_scheduler.py`：APScheduler 启停 + 两类任务注册。
- `water-info-ai/app/api/risk_scan.py`：FastAPI 路由 `POST /api/v1/flood/risk-scan/trigger`，签名 `{stationId, metricType, level}`，平台事件回调入口。
- `water-info-ai/app/services/assessment_writer.py`：把 RiskAssessor / PlanGenerator 的产物压成精简结构，调 `platform_client.upsert_ai_assessment`。
- 测试：`tests/test_risk_scan_scheduler.py`（mock graph，验证去抖、并发、写回）。

### 4.2 修改文件

- `water-info-ai/app/main.py`：FastAPI `lifespan` 中启动 / 停止 scheduler；路由注册。
- `water-info-ai/app/config.py`：新增字段
  - `risk_scan_periodic_minutes: int = 15`
  - `risk_scan_periodic_enabled: bool = True`
  - `risk_scan_event_debounce_seconds: int = 60`
- `water-info-ai/app/services/platform_client.py`：新增 `upsert_ai_assessment(payload)` → `POST /api/v1/ai-assessments`。
- `water-info-ai/app/graph.py`：新增**精简子图** `risk_only_graph`（DataAnalyst → RiskAssessor），用于周期巡检；事件触发用完整图但跳过 ResourceDispatcher / Notification，避免周期性误派人。

### 4.3 任务逻辑

```
class RiskScanScheduler:
    on startup:
        if cfg.risk_scan_periodic_enabled:
            scheduler.add_job(self._periodic_scan, IntervalTrigger(minutes=cfg.risk_scan_periodic_minutes),
                              id="periodic", coalesce=True, max_instances=1)

    async def _periodic_scan():
        stations = await db.list_active_stations()
        state = build_state(stations, mode="periodic")
        result = await risk_only_graph.ainvoke(state)
        await assessment_writer.write(result, source="PERIODIC")

    async def on_event(stationId, metricType, level):
        # 60s 内同 (station, metric) 的事件合并
        if debouncer.should_skip(stationId, metricType): return
        state = build_state([stationId], mode="event", trigger_level=level)
        result = await full_graph_minus_dispatch.ainvoke(state)
        await assessment_writer.write(result, source="EVENT")
```

要点：

- **并发控制**：APScheduler `max_instances=1` + asyncio Semaphore(2) 限制总并发，避免 LLM 突发调用导致限流。
- **超时**：每次 graph 执行 hard timeout 60s（asyncio.wait_for），超时即放弃本轮，下轮补。
- **去抖**：事件触发用 `(stationId, metricType)` 60s 滑窗，配合平台侧告警合并语义形成双层防抖。
- **写回幂等**：`ai-assessments` 表用 `(station_id, source, assessed_at_minute)` 唯一键，重复写回 upsert。
- **可观测**：Loguru 结构化日志 + Prometheus 指标（如已接入），事件队列堆积量打 WARN 阈值。

### 4.4 平台侧接收 AI 写回

- 新增 `module/aiassessment/`（实体 / mapper / service / controller）：
  - 表 `ai_assessment`：`id, station_id, metric_type, level, summary, plan_excerpt, source(PERIODIC|EVENT), assessed_at, created_at`
  - Flyway `V7__ai_assessment.sql`
  - REST：`GET /api/v1/ai-assessments?stationId&since` + `POST /api/v1/ai-assessments`（仅 AI 服务可调用，靠内网 + ServiceToken）
  - WebSocket：复用 `AlarmWebSocketHandler` 或开 `/ws/ai-assessments` 单独通道（推荐后者，避免污染告警语义）

---

## 5. 前端改动（`water-info-admin`）

- `views/ai/command/components/RiskPanel.vue`：增加"AI 巡检"标签页，订阅 `/ws/ai-assessments`，渲染最近一次研判摘要 + 时间戳 + 来源标签（PERIODIC / EVENT）。
- `views/ai/command/components/ActiveAlerts.vue`：在告警卡片上展示 `sourceTag`（SCHEDULED / MANUAL）以便运维区分。
- `composables/useWebSocket.ts`：支持多通道 client 实例。
- 不改路由结构，不增页面。

---

## 6. 配置（默认值）

```yaml
# water-info-platform application.yml
water-info:
  risk-scan:
    lightweight:
      enabled: true
      interval-ms: 90000        # 1.5 min
      window-seconds: 300       # 5 min observation 回看窗口
    ai:
      base-url: http://water-info-ai:8100
      service-token: ${AI_SERVICE_TOKEN}
      timeout-ms: 5000

# water-info-ai .env
RISK_SCAN_PERIODIC_ENABLED=true
RISK_SCAN_PERIODIC_MINUTES=15
RISK_SCAN_EVENT_DEBOUNCE_SECONDS=60
```

生产建议：演示/低负载环境 `interval-ms=120000`、`PERIODIC_MINUTES=30`；强降雨值守期可临时下调到 `60000` / `5`。

---

## 7. 落地步骤（建议顺序）

1. **DB 迁移**：`V6__alarm_open_unique_idx.sql`、`V7__ai_assessment.sql` 落库，本地 `./mvnw spring-boot:run` 验证 Flyway 通过。
2. **轻量层**：实现 `ScheduledRiskScanJob` + `RiskScanProperties` + 测试；docker-compose 起完整栈，构造越限 observation，确认 1–2 分钟内出告警 + WebSocket 推送。
3. **平台 → AI 事件回调**：实现 `WaterInfoAiClient` + 监听器；AI 侧先做最简 stub 路由（只打日志）打通链路。
4. **AI 写回接口**：平台侧 `ai-assessment` 模块 + AI 侧 `assessment_writer`；端到端写一条假数据校验。
5. **AI 调度器**：APScheduler 周期任务 + 事件任务接入；先用 `risk_only_graph` 跑通，再合入完整图。
6. **前端**：RiskPanel 接 `/ws/ai-assessments`、告警源标签展示。
7. **观测 & 调参**：跑半天，根据 LLM 调用量 / 告警密度调 `interval` 与 `debounce`。

---

## 8. 验收用例

| # | 场景 | 预期 |
|---|------|------|
| 1 | 单站水位越限（命中 HIGH 阈值）| ≤2 min 出告警；WebSocket 推送；触发 AI 事件研判，≤5 min 出 `ai-assessment` 记录 |
| 2 | 同站连续 3 次越限（同级别）| 仅 1 条 OPEN 告警；AI 事件被去抖合并（60s 窗内仅 1 次研判） |
| 3 | 越限从 HIGH 升级到 CRITICAL | 告警 level 升级（沿用现有 service 行为）；AI 事件再次触发研判 |
| 4 | AI 服务宕机 | 平台告警链路不受影响；事件回调失败仅打 WARN；AI 恢复后周期任务自然续上 |
| 5 | 平台 Job 宕机重启 | `@Scheduled` 重启即恢复，不依赖外部消息队列；不补跑历史窗口 |
| 6 | 演示离线 / 没有真实数据 | `lightweight.enabled=false` 一键关停轻量层；AI 周期任务用 `RISK_SCAN_PERIODIC_ENABLED=false` 关停；不影响其他功能 |

---

## 9. 风险与权衡

- **LLM 成本**：周期 15 分钟 × N 站点的全量研判可能放大 token 消耗。缓解：周期任务只跑 `risk_only_graph`（无 PlanGenerator），事件任务才跑完整图。
- **告警风暴**：阈值规则配置不当时，定时扫描会把现有问题"一次性炸出来"。上线前先用 `lightweight.enabled=false` 部署一轮，再人工抽检规则后开启。
- **时钟漂移**：观测 `observed_at` 与服务器时钟若偏差较大，会导致 `window` 漏数据。建议数据接入侧统一时区为 UTC，并在 Job 里以 `observed_at` 而非 `created_at` 做窗口判断。
- **耦合度**：平台 → AI 是单向 HTTP 调用，未引入 Kafka / RabbitMQ。如果未来事件量级提升或需重放，再升级到消息队列；当前规模不必。
