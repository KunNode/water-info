# 应急预案写入触发条件优化设计

## 背景

当前系统中，防汛应急预案由 `water-info-ai` 的 LangGraph 工作流生成。人工对话场景下，`supervisor` 会在用户命中“预案 / 方案 / 响应”等意图后推进到 `plan_generator`；接口结束后，`main._persist_result()` 只要发现最终状态中有 `emergency_plan`，就会写入 `emergency_plan` 及关联行动、资源、通知表。

自动事件场景下，`risk_event_graph` 已经能执行 `data_analyst -> risk_assessor -> plan_generator -> final_response`，并通过 `assessment_writer` 把 AI 研判写回平台。但预案生成、预案落库、预案触发条件文本目前没有统一策略。

现有风险是：

1. 预案“生成”和“写入预案库”边界不清，后续容易出现低风险或普通问答误写入。
2. 自动事件如果直接写入预案库，可能在连续告警中重复刷库。
3. `trigger_conditions` 可能只保留“综合风险达到响应阈值”这类泛化文本，缺少可审计的站点、指标、告警和依据。

## 目标

1. 明确区分预案生成和预案落库。
2. 自动事件与人工请求采用不同写入规则。
3. 自动事件在中高风险且证据明确时写入或更新事件预案。
4. 人工明确请求生成 / 保存预案时，每次新建预案，保留方案对比空间。
5. `trigger_conditions` 采用“摘要 + 结构化依据”，能够支撑详情页展示和审计追溯。
6. 将写入策略集中在一个轻量模块中，避免规则散落在 `main.py`、`risk_scan_scheduler.py` 和 `plan_generator.py`。

## 非目标

1. 不重写 LangGraph 主流程。
2. 不改变风险评估模型的评分算法。
3. 第一阶段不强制新增数据库字段或唯一索引。
4. 不把低风险自动巡检建议写入预案库。
5. 不要求前端在第一阶段新增预案编辑能力。

## 推荐方案

采用“应用层预案写入策略门”，保留数据库层幂等字段作为后续扩展点。

新增一个集中策略模块，例如：

```text
water-info-ai/app/services/plan_persistence.py
```

该模块负责三类判断：

1. `should_persist_plan(state, source) -> Decision`
2. `build_trigger_conditions(state, source) -> str`
3. `resolve_event_plan_identity(state) -> optional event key / existing plan id`

`plan_generator` 仍负责生成预案草案；保存前由策略模块决定是否落库，并覆盖或补强 `trigger_conditions`。这样 LLM 可以参与生成方案，但不能单独决定“是否入库”和“触发依据是什么”。

## 触发与落库策略

### 人工对话

当用户明确表达“生成预案 / 制定方案 / 保存预案 / 写入预案 / 应急响应方案”等意图时，可以写入预案库。

规则：

1. 每次人工明确请求都新建预案。
2. 即使风险等级为 `low`，也允许落库。
3. 低风险人工草案必须在 `trigger_conditions` 中说明：这是人工请求生成，当前风险未达到自动事件入库门槛。
4. 普通风险问答、站点状态查询、知识库问答不应因为中间状态产生 `emergency_plan` 就自动落库。

### 自动事件

自动事件包括高等级告警事件触发的 `risk_event_graph`，以及后续接入的事件型风险扫描。

自动事件只有满足以下条件才写入或更新事件预案：

1. 风险等级为 `moderate`、`high` 或 `critical`。
2. 触发证据明确，至少包含以下之一：
   - 站点和指标。
   - 活跃告警或告警等级。
   - 当前值、警戒线、危险线或阈值命中信息。
   - RAG evidence 中的响应等级或处置依据。
3. 来源为自动事件，不能由普通周期巡检 `low/none` 风险隐式升级为预案落库。

`none/low` 自动巡检只写 AI 研判和 `planExcerpt`，不进入 `emergency_plan`。

## 事件合并与预案身份

### 人工请求

人工请求保持现有 `EP-YYYYMMDD-XXXX` 形式，每次新建。

原因：

1. 用户可能希望比较多套方案。
2. 新建更符合“人工草案”的审计习惯。
3. 不需要推断用户是否想覆盖旧预案。

### 自动事件

自动事件默认合并，避免连续告警刷库。

第一阶段建议使用应用层事件身份，不新增 schema：

```text
session_id = risk-event:<station_id>:<metric_type>:<window>
trigger_conditions 包含 来源：自动事件
status = draft
```

保存前查询最近 30 分钟内同站点、同指标、同来源、未完成的事件预案：

1. 找到同窗口事件预案：复用其 `plan_id` 更新内容。
2. 未找到：新建事件预案。
3. 风险等级升级时新建升级版预案，避免把 III 级预案静默改成 II/I 级而丢失历史。
4. 超过合并窗口后新建。

后续如果出现并发重复写入，再增加数据库字段：

```text
source
event_key
trigger_fingerprint
```

并在 `(source, event_key)` 上增加唯一约束。

## `trigger_conditions` 格式

`trigger_conditions` 使用“摘要 + 结构化依据”。

示例：

```text
摘要：翠屏湖心水位 4.35m 超危险线 4.15m，且存在 2 条活跃告警，触发 II级响应预案。

关键依据：
1. 风险等级：high，综合评分 82.5，响应等级 II级响应。
2. 站点指标：翠屏湖心水位站 WATER_LEVEL 当前值 4.35m，警戒线 3.60m，危险线 4.15m。
3. 告警事件：当前存在 2 条 OPEN/ACK 告警，最高等级 CRITICAL。
4. 业务依据：[1]《防汛响应等级划分与启动条件》。
5. 来源：自动事件触发，station=ST_CP_LAKE_01，metric=WATER_LEVEL。
```

生成规则：

1. 必须包含来源：人工请求、自动事件或其他明确来源。
2. 必须包含风险等级，以及响应等级或风险评分。
3. 必须包含核心触发原因。
4. 有站点数据时写入站点、指标、当前值、警戒线、危险线。
5. 有告警数据时写入告警数量、最高告警等级和 OPEN/ACK 状态。
6. 有 RAG evidence 时保留引用编号和文档标题。
7. 没有 evidence 时不编造制度依据。
8. 文本控制在 1200 字以内。

低风险人工请求示例：

```text
摘要：人工请求生成防汛应急预案；当前综合风险为 low，未达到自动事件入库门槛，本预案作为人工草案保存。

关键依据：
1. 风险等级：low，综合评分 18.0。
2. 来源：人工对话请求。
3. 自动入库判断：未满足 moderate/high/critical 自动事件触发条件。
```

## 数据流

人工对话：

```text
用户请求
  -> flood_response_graph
  -> plan_generator 生成草案
  -> _persist_result
  -> plan_persistence.should_persist_plan(source="manual")
  -> build_trigger_conditions
  -> save_emergency_plan
```

自动事件：

```text
告警/事件触发
  -> risk_event_graph
  -> plan_generator 生成草案
  -> assessment_writer 写 AI 研判
  -> plan_persistence.should_persist_plan(source="event")
  -> resolve_event_plan_identity
  -> build_trigger_conditions
  -> save_emergency_plan 或跳过
```

周期巡检：

```text
periodic risk scan
  -> risk_only_graph
  -> assessment_writer 写 AI 研判
  -> none/low 不写预案库
```

## 组件边界

### `plan_generator`

继续负责生成预案草案，包括行动、资源、通知和初步摘要。

不负责：

1. 判断是否写入预案库。
2. 生成最终可审计的 `trigger_conditions`。
3. 判断自动事件是否合并到旧预案。

### `plan_persistence`

负责写入策略和触发条件构建。

建议数据结构：

```python
@dataclass
class PlanPersistenceDecision:
    should_persist: bool
    source: str
    mode: str  # create | update | skip
    reason: str
    plan_id: str | None = None
```

### `main._persist_result`

继续保存 conversation snapshot。

预案保存前必须调用 `plan_persistence`。策略返回 `skip` 时，不调用 `save_emergency_plan`，但接口响应仍可返回当前生成结果，避免破坏用户体验。

### `risk_scan_scheduler`

事件扫描在 `write_assessment()` 后，可以复用同一策略保存事件预案。低风险周期巡检不写预案库。

## 测试设计

### 策略单元测试

新增 `tests/test_plan_persistence.py`，覆盖：

1. 人工明确生成 + `low` 风险：允许新建，原因标记人工请求。
2. 自动事件 + `low/none`：不落库。
3. 自动事件 + `moderate/high/critical` + 有证据：允许落库。
4. 自动事件 + `moderate` 但无站点、指标、告警或依据：不落库。
5. `trigger_conditions` 必含来源、风险等级、关键依据。
6. 无 evidence 时不生成伪引用。

### 持久化入口测试

调整 `tests/test_main_api.py`：

1. 明确生成预案的人工请求仍会调用 `save_emergency_plan`。
2. 风险问答或普通态势查询不因存在中间预案对象而落库。
3. snapshot 仍然保存，不受预案跳过影响。

### 事件合并测试

覆盖：

1. 窗口内重复自动事件复用 `plan_id`。
2. 超过窗口新建。
3. 风险升级新建。
4. 查询旧事件预案失败时降级为新建，不阻断 AI 研判写回。

### 回归测试

保留现有能力：

1. 明确生成预案后接口响应仍返回 `plan_id`、`plan_name`、`actions_count`。
2. `plan_update` SSE 事件仍能发出。
3. `plan_generator` 兜底模板仍可在 LLM 不可用时生成完整草案。

建议验证命令：

```bash
cd water-info-ai
uv run pytest -q tests/test_plan_persistence.py tests/test_main_api.py tests/test_agents.py tests/test_supervisor_routing.py
```

## 验收标准

1. 自动事件 `moderate/high/critical` 且证据明确时，能写入或更新事件预案。
2. 自动事件 `none/low` 不污染预案库。
3. 人工明确请求生成预案时，每次新建。
4. 自动事件窗口内重复触发时合并更新，风险升级或超过窗口时新建。
5. `trigger_conditions` 包含摘要、风险等级、响应等级或评分、站点指标、告警信息、来源和可选引用。
6. 没有 RAG evidence 时，不编造制度依据。
7. 现有 AI 指挥台获取 `plan_id/plan_name/actions_count` 的行为不被破坏。

## 风险与对策

1. 风险：不新增 schema 时，事件预案身份依赖 `session_id` 和文本约定，长期可维护性一般。  
   对策：第一阶段先控范围；如果出现并发重复或查询困难，再增加 `source/event_key/trigger_fingerprint` 字段和唯一约束。

2. 风险：人工请求识别过宽，仍可能把普通问答落库。  
   对策：策略中使用明确动词和 intent 双重判断，测试覆盖“风险评估但不要求生成预案”的场景。

3. 风险：`trigger_conditions` 过长影响列表展示。  
   对策：字段控制在 1200 字以内；列表页展示摘要首行，详情页展示完整依据。

4. 风险：事件扫描保存预案失败影响 AI 研判写回。  
   对策：预案保存失败应记录 warning，不回滚 `assessment_writer` 的 AI 研判写回。

## 实施边界

第一阶段建议改动范围：

1. `water-info-ai/app/services/plan_persistence.py`
2. `water-info-ai/app/main.py`
3. `water-info-ai/app/services/risk_scan_scheduler.py`
4. `water-info-ai/app/database.py` 中补充最近事件预案查询方法
5. `water-info-ai/tests/test_plan_persistence.py`
6. `water-info-ai/tests/test_main_api.py`
7. 必要时补充 `water-info-ai/tests/test_risk_scan_scheduler.py`

不建议第一阶段修改：

1. 平台 Spring 数据库 schema。
2. 前端页面结构。
3. 风险评分算法。
