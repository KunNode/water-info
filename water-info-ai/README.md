# 🌊 水务AI多智能体防洪应急预案系统

基于 **LangGraph** 的多智能体协作系统，用于防洪应急预案的智能生成与执行监控。

## 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Service (:8100)                   │
│   /api/v1/flood/query       /api/v1/flood/query/stream      │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                  LangGraph Workflow                          │
│                                                              │
│  ┌──────────┐                                                │
│  │Supervisor│──────────── 路由决策 ──────────────┐            │
│  └────┬─────┘                                   │            │
│       │                                          │            │
│  ┌────▼──────────┐  ┌────────────────┐  ┌───────▼────────┐  │
│  │ DataAnalyst   │  │ RiskAssessor   │  │ PlanGenerator  │  │
│  │ 数据采集分析   │  │ 风险等级评估   │  │ 预案生成       │  │
│  └───────────────┘  └────────────────┘  └────────────────┘  │
│                                                              │
│  ┌────────────────┐  ┌────────────────┐  ┌───────────────┐  │
│  │ResourceDispatch│  │ Notification   │  │ExecutionMonitor│ │
│  │ 资源调度       │  │ 预警通知       │  │ 执行监控       │  │
│  └────────────────┘  └────────────────┘  └───────────────┘  │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │              FinalResponse 汇总输出                    │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│             water-info-platform (Spring Boot :8080)          │
│   /api/v1/stations  /observations  /alarms  /threshold-rules│
└─────────────────────────────────────────────────────────────┘
```

## 智能体说明

| 智能体 | 职责 | 工具 |
|--------|------|------|
| **Supervisor** | 理解用户意图，路由任务到子智能体 | - |
| **DataAnalyst** | 采集水位、雨量、告警等实时数据 | fetch_all_stations, fetch_station_observations, fetch_active_alarms, fetch_threshold_rules, fetch_sensors_status |
| **RiskAssessor** | 量化评估洪水风险等级 | calculate_water_level_risk, calculate_rainfall_risk, calculate_composite_risk |
| **PlanGenerator** | 生成应急响应预案 | generate_plan_id, get_response_template, lookup_emergency_contacts |
| **ResourceDispatcher** | 制定人员物资调度方案 | - |
| **Notification** | 制定预警通知方案 | - |
| **ExecutionMonitor** | 监控预案执行进度 | - |

## 快速开始

### 1. 环境准备

```bash
cd water-info-ai

# 创建虚拟环境
python -m venv .venv

# 激活 (Windows)
.venv\Scripts\activate

# 安装依赖
pip install -e .
```

### 2. 配置

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件，配置：
# - OPENAI_API_KEY (或本地模型地址)
# - WATER_PLATFORM_BASE_URL (水务平台后端地址)
```

### 3. 启动服务

```bash
# 确保 water-info-platform (Spring Boot) 已启动

# 启动 AI 服务
python -m app.main
```

服务启动后访问: http://localhost:8100/docs (Swagger UI)

### 4. 使用示例

**普通请求:**
```bash
curl -X POST http://localhost:8100/api/v1/flood/query \
  -H "Content-Type: application/json" \
  -d '{"query": "分析当前水情并生成防洪应急预案"}'
```

**流式请求 (SSE):**
```bash
curl -N http://localhost:8100/api/v1/flood/query/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "制定完整的防洪应急响应方案"}'
```

## 项目结构

```
water-info-ai/
├── app/
│   ├── __init__.py
│   ├── config.py              # 配置管理
│   ├── state.py               # 共享状态定义
│   ├── graph.py               # LangGraph 工作流图
│   ├── main.py                # FastAPI 入口
│   ├── agents/                # 智能体节点
│   │   ├── supervisor.py      # Supervisor 路由
│   │   ├── data_analyst.py    # 数据分析
│   │   ├── risk_assessor.py   # 风险评估
│   │   ├── plan_generator.py  # 预案生成
│   │   ├── resource_dispatcher.py  # 资源调度
│   │   ├── notification_agent.py   # 通知管理
│   │   ├── execution_monitor.py    # 执行监控
│   │   └── final_response.py       # 最终汇总
│   ├── tools/                 # 智能体工具
│   │   ├── data_tools.py      # 数据采集工具
│   │   ├── risk_tools.py      # 风险计算工具
│   │   └── plan_tools.py      # 预案模板工具
│   └── services/              # 服务层
│       ├── llm.py             # LLM 实例工厂
│       └── platform_client.py # 水务平台 API 客户端
├── tests/                     # 测试
├── pyproject.toml             # 项目配置
├── .env.example               # 环境变量模板
└── README.md
```

## 工作流示例

用户请求 "制定完整的防洪应急响应方案" 时，工作流如下：

```
1. Supervisor 分析意图 → 路由到 DataAnalyst
2. DataAnalyst 采集水位/雨量/告警数据 → 生成数据摘要 → 回到 Supervisor
3. Supervisor 判断需要风险评估 → 路由到 RiskAssessor
4. RiskAssessor 量化风险等级 → 回到 Supervisor
5. Supervisor 判断需要生成预案 → 路由到 PlanGenerator
6. PlanGenerator 生成应急预案 → 回到 Supervisor
7. Supervisor 判断需要资源调度 → 路由到 ResourceDispatcher
8. ResourceDispatcher 制定调度方案 → 回到 Supervisor
9. Supervisor 判断需要通知方案 → 路由到 Notification
10. Notification 制定通知方案 → 回到 Supervisor
11. Supervisor 判断工作完成 → 路由到 __end__
12. FinalResponse 汇总所有结果 → 输出完整报告
```

## 与现有系统的集成

本 AI 服务作为独立微服务运行，通过 HTTP API 与现有系统集成：

- **上游**: 调用 `water-info-platform` (Spring Boot) 的 REST API 获取数据
- **下游**: 提供 REST API 和 SSE 流式接口供 `water-info-admin` (Vue 前端) 调用
- **可扩展**: 后续可集成气象API、GIS服务、第三方通知平台等

## 风险等级体系

| 等级 | 颜色 | 响应级别 | 说明 |
|------|------|----------|------|
| none | - | 无需响应 | 正常水平 |
| low | 🔵 蓝 | IV级 (一般) | 接近警戒水位 |
| moderate | 🟡 黄 | III级 (较大) | 达到警戒水位 |
| high | 🟠 橙 | II级 (重大) | 接近危险水位 |
| critical | 🔴 红 | I级 (特别重大) | 超过危险水位 |

## 技术栈

- **Python 3.11+**
- **LangGraph** — 多智能体工作流编排
- **LangChain** — LLM 交互框架
- **FastAPI** — HTTP API 服务
- **Pydantic** — 数据验证
- **httpx** — 异步 HTTP 客户端
- **loguru** — 日志框架
