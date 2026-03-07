# 智慧水利防汛应急管理系统

基于 Spring Boot + FastAPI + LangGraph 的多智能体协作防洪应急管理平台。

## 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                          前端 (Vue 3)                            │
│                     http://localhost:5173                       │
└───────────────────────────┬─────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│  Nginx       │   │ Spring Boot  │   │  FastAPI AI  │
│  :80         │   │  :8080       │   │  :8100       │
│  反向代理     │   │  业务API      │   │  AI服务      │
└──────┬───────┘   └──────┬───────┘   └──────┬───────┘
       │                  │                   │
       └──────────────────┼───────────────────┘
                          │
       ┌──────────────────┼──────────────────┐
       ▼                  ▼                  ▼
┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│  PostgreSQL │   │    Redis    │   │   AI/LLM    │
│  业务数据   │   │  缓存/会话  │   │  DeepSeek   │
└─────────────┘   └─────────────┘   └─────────────┘
```

## 技术栈

### 后端 (water-info-platform)
- **框架**: Spring Boot 3.2.2
- **语言**: Java 17
- **ORM**: MyBatis-Plus 3.5.5
- **数据库**: PostgreSQL 15
- **缓存**: Redis + Caffeine
- **安全**: Spring Security + JWT
- **文档**: OpenAPI 3.0 + Knife4j
- **测试**: JUnit 5 + Testcontainers

### AI 服务 (water-info-ai)
- **框架**: FastAPI 0.115+
- **语言**: Python 3.11+
- **AI 编排**: LangGraph 0.2+ / LangChain 0.3+
- **模型**: DeepSeek / OpenAI
- **数据库**: asyncpg (PostgreSQL 异步驱动)
- **缓存**: Redis
- **测试**: pytest + pytest-asyncio

## 功能特性

### 核心功能
- 🏭 **监测站管理** - 水位站、雨量站、流量站等基础信息管理
- 📊 **实时数据** - 水情数据批量采集与查询（支持5000条批量上传）
- 🚨 **智能告警** - 基于阈值的自动告警，支持状态机流转（OPEN→ACK→CLOSED）
- 📈 **风险预警** - AI 驱动的洪水风险等级评估（蓝/黄/橙/红四级）
- 📝 **应急预案** - 多智能体协作生成防洪应急预案
- 🔔 **实时推送** - WebSocket 告警实时推送
- 👥 **权限管理** - RBAC 权限模型（ADMIN/OPERATOR/VIEWER）

### AI 智能体

| 智能体 | 职责 | 关键工具 |
|--------|------|----------|
| **Supervisor** | 意图理解与任务路由 | - |
| **DataAnalyst** | 水情数据采集与分析 | fetch_stations, fetch_observations, fetch_alarms |
| **RiskAssessor** | 洪水风险等级评估 | calculate_water_level_risk, calculate_rainfall_risk |
| **PlanGenerator** | 应急预案生成 | generate_plan_id, get_response_template |
| **ResourceDispatcher** | 资源调度方案 | - |
| **Notification** | 预警通知方案 | - |

## 快速开始

### 环境要求
- Java 17+
- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- Maven 3.8+

### 1. 克隆项目

```bash
git clone <repository-url>
cd code-work
```

### 2. 启动基础设施

```bash
# 使用 Docker 启动 PostgreSQL 和 Redis
docker-compose up -d postgres redis
```

### 3. 启动后端服务

```bash
cd water-info-platform

# 编译
./mvnw clean package -DskipTests

# 运行（开发环境）
./mvnw spring-boot:run -Dspring-boot.run.profiles=dev

# 或运行 jar
java -jar target/water-info-platform-1.0.0-SNAPSHOT.jar
```

后端服务启动后访问：
- API 文档: http://localhost:8080/swagger-ui.html
- Knife4j: http://localhost:8080/doc.html

### 4. 启动 AI 服务

```bash
cd water-info-ai

# 创建虚拟环境
python -m venv .venv

# 激活（Windows）
.venv\Scripts\activate

# 激活（Linux/Mac）
source .venv/bin/activate

# 安装依赖
pip install -e ".[dev]"

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，配置 OPENAI_API_KEY 等

# 启动服务
python -m app.main
```

AI 服务启动后访问：
- Swagger UI: http://localhost:8100/docs
- ReDoc: http://localhost:8100/redoc

### 5. 使用 Docker Compose 一键启动

```bash
# 启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

## API 示例

### 用户登录
```bash
curl -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "Admin@123456"}'
```

### 查询监测站
```bash
curl -X GET "http://localhost:8080/api/v1/stations?page=1&size=10" \
  -H "Authorization: Bearer <token>"
```

### AI 防洪查询
```bash
# 普通请求
curl -X POST http://localhost:8100/api/v1/flood/query \
  -H "Content-Type: application/json" \
  -d '{"query": "分析当前水情并生成防洪应急预案"}'

# 流式请求（SSE）
curl -N http://localhost:8100/api/v1/flood/query/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "制定完整的防洪应急响应方案"}'
```

## 项目结构

```
code-work/
├── water-info-platform/          # Spring Boot 后端
│   ├── src/main/java/com/waterinfo/platform/
│   │   ├── common/               # 通用组件（异常、API响应、工具类）
│   │   ├── config/               # 配置类
│   │   ├── module/               # 业务模块
│   │   │   ├── station/          # 监测站管理
│   │   │   ├── observation/      # 观测数据
│   │   │   ├── alarm/            # 告警管理
│   │   │   ├── threshold/        # 阈值规则
│   │   │   ├── user/             # 用户权限
│   │   │   └── auth/             # 认证授权
│   │   └── security/             # Spring Security 配置
│   ├── src/main/resources/
│   │   ├── db/migration/         # Flyway 数据库迁移脚本
│   │   ├── application.yml       # 主配置
│   │   ├── application-dev.yml   # 开发环境配置
│   │   └── application-prod.yml  # 生产环境配置
│   └── Dockerfile
│
├── water-info-ai/                # FastAPI AI 服务
│   ├── app/
│   │   ├── agents/               # LangGraph 智能体
│   │   │   ├── supervisor.py     # 路由决策
│   │   │   ├── data_analyst.py   # 数据分析
│   │   │   ├── risk_assessor.py  # 风险评估
│   │   │   └── plan_generator.py # 预案生成
│   │   ├── tools/                # 智能体工具
│   │   ├── services/             # 服务层（数据库、LLM）
│   │   ├── config.py             # 配置
│   │   ├── state.py              # 状态定义
│   │   ├── graph.py              # 工作流图
│   │   └── main.py               # FastAPI 入口
│   ├── tests/                    # 测试
│   ├── pyproject.toml            # 项目配置
│   ├── .env.example              # 环境变量模板
│   └── Dockerfile
│
├── docker-compose.yml            # Docker 编排
├── nginx.conf                    # Nginx 配置
└── README.md                     # 本文件
```

## 开发指南

### 后端开发

```bash
cd water-info-platform

# 编译
./mvnw clean compile

# 运行测试
./mvnw test

# 运行单个测试
./mvnw test -Dtest=StationServiceTest

# 打包
./mvnw package -DskipTests
```

### AI 服务开发

```bash
cd water-info-ai

# 安装依赖
pip install -e ".[dev]"

# 运行测试
pytest tests/ -v

# 运行单个测试
pytest tests/test_agents.py::TestSupervisorAgent -v

# 代码检查
ruff check app/ tests/

# 格式化代码
ruff format app/ tests/
```

## 部署指南

### 生产环境配置

1. **数据库**: 配置生产级 PostgreSQL，执行迁移脚本
2. **Redis**: 配置持久化和认证
3. **环境变量**: 修改 `application-prod.yml` 和 `.env`
4. **JWT**: 更换生产环境密钥
5. **日志**: 配置 JSON 格式日志收集

### 使用 Docker 部署

```bash
# 构建镜像
docker-compose build

# 启动生产环境
docker-compose -f docker-compose.yml up -d

# 查看日志
docker-compose logs -f platform
docker-compose logs -f ai-service
```

### 监控与运维

- **健康检查**: `GET /actuator/health`
- **指标监控**: `GET /actuator/prometheus`
- **API 文档**: `/swagger-ui.html`, `/doc.html`

## 风险等级体系

| 等级 | 颜色 | 响应级别 | 触发条件 |
|------|------|----------|----------|
| none | - | 无需响应 | 正常水平 |
| low | 🔵 蓝 | IV级 | 接近警戒水位 |
| moderate | 🟡 黄 | III级 | 达到警戒水位 |
| high | 🟠 橙 | II级 | 接近危险水位 |
| critical | 🔴 红 | I级 | 超过危险水位 |

## 贡献指南

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`) 
## 许可证

[MIT](LICENSE)

## 联系方式

如有问题或建议，欢迎提交 Issue 或 Pull Request。
