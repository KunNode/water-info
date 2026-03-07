# 多智能体路由修复设计方案

**日期**: 2026-03-02  
**状态**: 已确认，待实现  
**方案**: B — 确定性路由引擎  

---

## 1. 问题描述

### 现象
AI 服务运行时，SSE 流持续输出：
```
{"node": "supervisor", "session_id": "..."}
{"node": "resource_dispatcher", "session_id": "..."}
{"node": "supervisor", "session_id": "..."}
{"node": "resource_dispatcher", "session_id": "..."}
...
```
死循环直到迭代上限（8次）强制终止。

### 根本原因

**原因 1 — Supervisor 纯 LLM 路由，无确定性终止条件**

当前 `supervisor.py` 完全依赖 LLM 决定 `next_agent`。当 `resource_plan` 已存在但 `notifications` 为空时，LLM 误判"工作未完成"，反复路由回 `resource_dispatcher`。

```
用户: "调度应急资源"
  → supervisor (LLM判断: 直接去resource_dispatcher)
  → resource_dispatcher (设置resource_plan)
  → supervisor (LLM判断: notifications为空，再去resource_dispatcher)  ← 死循环
  → resource_dispatcher ...
```

**原因 2 — SSE 流格式与前端不匹配**

`main.py` SSE 流只输出原始节点名称，前端 `useSSE.ts` 期望结构化事件类型：
```typescript
// 前端期望
{ type: 'agent_update', agent: string, status: 'active' | 'done' | 'failed' }
{ type: 'risk_update', level: string, details?: string[] }
{ type: 'plan_update', name: string, status: string, total: number, completed: number, failed: number }
{ type: 'session_init', sessionId: string }

// 后端实际输出
{ node: 'supervisor', session_id: '...' }
{ node: 'resource_dispatcher', session_id: '...' }
```

**原因 3 — Windows 日志编码问题（次要）**

- `UnicodeEncodeError: 'gbk'`：日志中包含 emoji（`ℹ️`），Windows GBK 控制台无法输出
- `KeyError: 'trace_id'`：Loguru JSON 格式模板引用了未注入的 extra 字段

---

## 2. 方案 B：确定性路由引擎

### 设计原则

> **规则引擎优先，LLM 兜底**

将 Supervisor 的路由逻辑分为两层：

1. **确定性规则层**（代码）：根据 state 字段的存在/缺失，直接判断下一步
2. **LLM 兜底层**：仅当规则层无法判断时（如复杂用户意图），才调用 LLM

### 路由状态机设计

```
用户请求
    │
    ▼
[意图分类] ─── 规则判断 ───────────────────────────────────────────────┐
    │                                                                      │
    │ "完整应急响应"类                                                     │ "仅查数据"类
    ▼                                                                      ▼
[data_summary 存在?]                                            [data_analyst → __end__]
    │ 否 → data_analyst
    │ 是
    ▼
[risk_assessment 存在?]
    │ 否 → risk_assessor
    │ 是
    ▼
[emergency_plan.plan_id 非空?]
    │ 否 → plan_generator
    │ 是
    ▼
[resource_plan 存在 AND notifications 存在?]
    │ 否 → parallel_dispatch（两者都缺）
    │ 仅 resource_plan 缺 → resource_dispatcher
    │ 仅 notifications 缺 → notification
    │ 是
    ▼
[final_response 存在?]
    │ 否 → __end__（触发 final_response 节点）
    │ 是 → __end__
```

### 意图分类规则

```python
INTENT_RULES = {
    # 完整应急响应流水线
    "full_response": ["应急", "预案", "响应", "调度", "通知", "完整"],
    # 仅数据查询
    "data_only": ["水位", "雨量", "数据", "查询", "当前", "实时"],
    # 仅风险评估
    "risk_only": ["风险", "威胁", "是否", "评估"],
    # 仅执行监控
    "monitor_only": ["进度", "执行", "完成", "监控"],
}
```

---

## 3. 文件改动清单

### 3.1 `water-info-ai/app/agents/supervisor.py` ⭐ 主要改动

**新增函数 `_deterministic_route(state, intent)`**：
```python
def _deterministic_route(state: FloodResponseState, intent: str) -> str | None:
    """
    确定性路由规则。返回 None 表示无法确定，需要 LLM 决策。
    """
    # 终止条件：达到最大迭代
    if state.get("iteration", 0) >= 8:
        return "__end__"

    # 完整流水线终止条件
    if (state.get("resource_plan") and state.get("notifications")):
        return "__end__"

    # 监控意图
    if intent == "monitor_only":
        return "execution_monitor"

    # 仅数据查询
    if intent == "data_only":
        if not state.get("data_summary"):
            return "data_analyst"
        return "__end__"

    # 完整流水线（按顺序推进）
    if not state.get("data_summary"):
        return "data_analyst"
    if not state.get("risk_assessment"):
        return "risk_assessor"
    if not (state.get("emergency_plan") and state["emergency_plan"].plan_id):
        return "plan_generator"
    # resource_plan 和 notifications 都缺 → parallel_dispatch
    has_resource = bool(state.get("resource_plan"))
    has_notifications = bool(state.get("notifications"))
    if not has_resource and not has_notifications:
        return "parallel_dispatch"
    if not has_resource:
        return "resource_dispatcher"
    if not has_notifications:
        return "notification"
    return "__end__"
```

**修改 `supervisor_node`**：
- 先做意图分类（关键词匹配）
- 调用 `_deterministic_route`
- 仅当返回 `None` 时调用 LLM

### 3.2 `water-info-ai/app/main.py` ⭐ SSE 格式修复

**新增 `_state_to_sse_events(node_name, state)` 函数**：
```python
def _state_to_sse_events(node_name: str, state: dict) -> list[dict]:
    events = []
    # 总是发 agent_update
    events.append({"type": "agent_update", "agent": node_name, "status": "done"})
    # 风险更新
    if node_name == "risk_assessor" and state.get("risk_assessment"):
        ra = state["risk_assessment"]
        events.append({
            "type": "risk_update",
            "level": ra.get("risk_level", "none"),
            "details": ra.get("key_risks", [])
        })
    # 预案更新
    if node_name in ("plan_generator", "parallel_dispatch") and state.get("emergency_plan"):
        ep = state["emergency_plan"]
        prog = state.get("execution_progress", {})
        events.append({
            "type": "plan_update",
            "name": ep.get("plan_name", ""),
            "status": ep.get("status", "draft"),
            "total": prog.get("total_actions", len(ep.get("actions", []))),
            "completed": prog.get("completed_actions", 0),
            "failed": prog.get("failed_actions", 0),
        })
    return events
```

**修改 SSE stream 逻辑**：在每个节点流出时，调用 `_state_to_sse_events` 输出结构化事件。

### 3.3 `water-info-ai/app/utils/log_config.py`（新建）日志修复

```python
import sys
from loguru import logger

def configure_logging(json_logs: bool = False):
    logger.remove()
    if json_logs:
        logger.add(sys.stderr, serialize=True, enqueue=True)
    else:
        # Windows 兼容：强制 UTF-8，去掉 emoji
        logger.add(
            sys.stderr,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | {message}",
            encoding="utf-8",
            enqueue=True,
        )
```

---

## 4. 不改动的文件

| 文件 | 原因 |
|------|------|
| `app/graph.py` | 图结构本身正确，无需改动 |
| `app/state.py` | 状态定义完整，无需改动 |
| `app/agents/resource_dispatcher.py` | 逻辑正确，问题在路由层 |
| `app/agents/parallel_dispatch.py` | 逻辑正确 |
| 所有前端文件 | 前端 SSE 事件格式已正确定义，不改动 |

---

## 5. 验证标准

实现完成后，需满足以下验证条件：

### 功能验证
- [ ] 发送"查询当前水位" → 只走 `data_analyst`，一次即结束
- [ ] 发送"生成应急预案" → 按序走 `data_analyst → risk_assessor → plan_generator → parallel_dispatch → final_response`，无循环
- [ ] 发送"调度应急资源" → 不再死循环，正确补全前置步骤后终止
- [ ] 迭代次数 ≤ 7（不触发强制终止）

### 前端验证
- [ ] SSE 流能触发前端 `AgentTimeline` 组件更新（显示各 agent 状态）
- [ ] 风险评估完成后，前端 `risk_update` 事件触发，风险等级显示正确
- [ ] 预案生成后，前端 `plan_update` 事件触发，显示措施数量

### 日志验证
- [ ] Windows 控制台无 `UnicodeEncodeError`
- [ ] 无 `KeyError: 'trace_id'` 警告

---

## 6. 实现顺序

1. `supervisor.py` — 确定性路由引擎（优先，解决死循环）
2. `main.py` — SSE 事件格式（次之，前端联调）
3. `log_config.py` — 日志修复（最后，次要问题）
4. 运行 `pytest tests/` 验证
5. 手动测试 3 个场景（见验证标准）
