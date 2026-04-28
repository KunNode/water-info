# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Smart Water Management and Flood Emergency Response System** with a multi-agent AI architecture. The system consists of three services:

- **water-info-platform** (Spring Boot 3.2.2, Java 17): REST API for station management, observations, alarms, thresholds, RBAC
- **water-info-ai** (Python 3.11, FastAPI, LangGraph): Multi-agent AI system for flood emergency plan generation
- **water-info-admin** (Vue 3, TypeScript, Vite): Admin dashboard frontend with Element Plus UI

## Architecture

### Service Communication

```
Frontend (:5173) → Nginx (:80) → Spring Boot (:8080) / FastAPI AI (:8100)
                                         ↕                    ↕
                                    PostgreSQL 15         PostgreSQL 15 (direct read via asyncpg)
                                    Redis 7               Redis 7 (sessions)
                                                          LLM API (DeepSeek)
```

**Critical data flow pattern**: The AI service reads directly from PostgreSQL (asyncpg) for low-latency queries, but writes through the Spring Boot REST API to maintain business logic consistency.

### Backend (water-info-platform)

Each module under `module/` follows a consistent structure: `entity/ → dto/ → vo/ → mapper/ → service/ → controller/`

**Key modules:**
- `station`: Station management (types: WATER_LEVEL, RAIN_GAUGE, FLOW, RESERVOIR, GATE, PUMP_STATION)
- `observation`: Time-series data with batch upload (max 5000 records)
- `alarm`: State machine (OPEN → ACK → CLOSED) with WebSocket real-time push via `AlarmWebSocketHandler`
- `threshold`: Configurable rules for triggering alarms
- `user`: RBAC with ADMIN/OPERATOR/VIEWER roles
- `audit`: Audit logging

### AI Service (water-info-ai)

**Multi-agent workflow (LangGraph):**
1. **Supervisor** (`agents/supervisor.py`): Routes user queries to appropriate agents
2. **DataAnalyst** (`agents/data_analyst.py`): Fetches real-time water level/rainfall/alarm data
3. **RiskAssessor** (`agents/risk_assessor.py`): Calculates risk levels (none/low/moderate/high/critical)
4. **PlanGenerator** (`agents/plan_generator.py`): Generates emergency response plans
5. **ResourceDispatcher** (`agents/resource_dispatcher.py`): Schedules personnel/materials
6. **Notification** (`agents/notification_agent.py`): Creates warning notification plans
7. **ExecutionMonitor** (`agents/execution_monitor.py`): Monitors plan execution

**Key files:**
- `app/state.py`: `FloodResponseState` TypedDict — shared state passed between agents with reducer-based message merging
- `app/graph.py`: LangGraph workflow definition with conditional edges for dynamic agent routing
- `app/tools/`: `@tool`-decorated async functions agents can call (data_tools, plan_tools, risk_tools, weather_tools)
- `app/services/database.py`: `DatabaseService` with asyncpg connection pool (min=2, max=10)
- `app/services/platform_client.py`: HTTP client for calling Spring Boot API

### Frontend (water-info-admin)

- **State**: Pinia stores (`stores/user.ts` for auth, `stores/app.ts` for UI state)
- **Real-time**: `composables/useWebSocket.ts` for alarm push, `composables/useSSE.ts` for AI streaming
- **RBAC**: `directives/permission.ts` custom directive for role-based UI rendering
- **API layer**: Axios client in `api/request.ts` with JWT token injection and error interceptors
- **Visualization**: ECharts for data charts, Leaflet for maps

## Build & Test Commands

### Backend (water-info-platform)

```bash
./mvnw clean compile                    # Build
./mvnw test                             # Run all tests
./mvnw test -Dtest=StationServiceTest   # Run single test class
./mvnw test -Dtest=StationServiceTest#shouldCreateStationSuccessfully  # Single test method
./mvnw package -DskipTests              # Package JAR
./mvnw spring-boot:run -Dspring-boot.run.profiles=dev  # Run locally (dev profile)
```

### AI Service (water-info-ai)

```bash
cd water-info-ai
uv sync --extra dev          # Install dependencies

uv run python -m app.main    # Run service

uv run pytest tests/         # Run all tests
uv run pytest tests/test_agents.py -v                                        # Single test file
uv run pytest tests/test_agents.py::TestSupervisorAgent::test_supervisor_routes_to_data_analyst_for_data_query -v  # Single test

uv run ruff check app/ tests/       # Lint
uv run ruff format app/ tests/      # Format
uv run mypy app/ --ignore-missing-imports  # Type check
```

### Frontend (water-info-admin)

```bash
cd water-info-admin
npm install                  # Install dependencies
npm run dev                  # Dev server (:5173)
npm run build                # Type check + production build (vue-tsc --noEmit && vite build)
npm run lint                 # ESLint with auto-fix
npm run format               # Prettier formatting
```

### Docker (All Services)

```bash
docker-compose up -d                    # Start all 6 services (postgres, redis, platform, ai, admin, nginx)
docker-compose build                    # Build images
docker-compose logs -f platform         # View backend logs
docker-compose logs -f ai-service       # View AI service logs
docker-compose down                     # Stop
```

## Key Patterns

### Backend
- **Exception handling**: `BusinessException` with `ErrorCode` enum, handled by `GlobalExceptionHandler`
- **Response format**: `ApiResponse<T>` wrapper with traceId, timestamp, pagination, metadata
- **Caching**: `@Cacheable`/`@CacheEvict` on StationService/ThresholdRuleService (Redis for distributed, Caffeine for local — 1000 items, 5m expiry)
- **WebSocket**: `AlarmWebSocketHandler` broadcasts alarm events to connected clients at `/ws/alarms`
- **Rate limiting**: `RateLimitConfig` — 100 req/min default, 5 req/min for login
- **Database IDs**: UUID auto-generation via MyBatis-Plus `ASSIGN_UUID`; soft delete via `deleted` field

### AI Service
- **Agent pattern**: Each agent implements `async def agent_node(state: FloodResponseState) -> FloodResponseState`
- **Tools**: `@tool` decorated async functions in `app/tools/`
- **Config**: Pydantic Settings loading from `.env` file (`app/config.py`)
- **Logging**: loguru with JSON or console format

## Database

PostgreSQL with Flyway migrations at `water-info-platform/src/main/resources/db/migration/`:
- `V1__water_info_schema.sql`: Core schema (stations, sensors, observations, alarms, thresholds, users)
- `V2__user_access_control.sql`: RBAC tables (sys_role, sys_user_role, sys_permission)
- `V3__legacy_public_compat.sql`: Legacy schema compatibility
- `V4__legacy_public_seed_test_data.sql`: Test data seeding
- `V5__performance_indexes.sql`: Performance indexes

Flyway runs automatically on startup. New migrations: `V{N}__{description}.sql`

## Testing

- **Backend**: JUnit 5 + Testcontainers (PostgreSQL container). Use `@ActiveProfiles("test")` for test config.
- **AI**: pytest + pytest-asyncio (asyncio_mode="auto") + mocks for external services
- **CI**: GitHub Actions (`.github/workflows/ci.yml`) runs backend build/test, AI lint/typecheck/test with coverage, Docker image build, and Trivy security scan

## API Endpoints

### Backend (:8080)
- `POST /api/v1/auth/login` — Authentication
- `GET/POST /api/v1/stations` — Station CRUD
- `POST /api/v1/observations/batch` — Batch observation upload
- `GET/POST /api/v1/alarms` — Alarm management
- `GET/POST /api/v1/threshold-rules` — Threshold configuration
- `GET /api/v1/audit-logs` — Audit trail
- `WS /ws/alarms` — WebSocket for real-time alarms
- `GET /swagger-ui.html` — API docs; `GET /doc.html` — Knife4j docs

### AI Service (:8100)
- `POST /api/v1/flood/query` — Execute AI workflow
- `POST /api/v1/flood/query/stream` — Streaming (SSE)
- `GET /api/v1/plans` — List emergency plans
- `GET /api/v1/plans/{id}` — Plan details
- `POST /api/v1/plans/{id}/execute` — Execute plan
- `GET /api/v1/sessions/{id}` — Session history
- `GET /docs` — Swagger UI

## Configuration

### Key Configuration Files
- `water-info-platform/src/main/resources/application.yml` — Main config (port, Redis, cache, JWT, rate limits)
- `water-info-platform/src/main/resources/application-dev.yml` / `application-prod.yml` — Environment configs
- `water-info-ai/.env` — AI service environment variables (copy from `.env.example`)
- `water-info-admin/vite.config.ts` — Frontend build config
- `nginx.conf` — Reverse proxy routing, rate limiting, WebSocket/SSE proxy settings
