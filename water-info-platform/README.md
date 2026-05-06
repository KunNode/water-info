# Water Info Platform

`water-info-platform` is the Spring Boot service layer for the smart water management and flood emergency response system. It owns authentication, RBAC, station/sensor/observation data, alarms, thresholds, resources, audit logs, WebSocket push, and the Java-side proxy for the Python AI service.

## Stack

| Area | Technology |
| --- | --- |
| Runtime | Java 17 |
| Framework | Spring Boot 3.2.2 |
| Persistence | MyBatis-Plus 3.5.5 |
| Database | PostgreSQL 15+ |
| Migration | Flyway 10.8.1 |
| Cache | Caffeine local cache, Redis integration |
| Security | Spring Security, JWT, method-level `@PreAuthorize` |
| API docs | Springdoc OpenAPI, Swagger UI, Knife4j |
| Testing | JUnit 5, Spring Security Test, Testcontainers |

The repository currently does not include a Maven Wrapper, so use a local `mvn` installation.

## Module Map

Each business module follows the same general shape:

```text
entity -> dto -> vo -> mapper -> service -> controller
```

| Module | Package | Responsibility |
| --- | --- | --- |
| Auth | `module/auth` | Login, current user, logout |
| User/RBAC | `module/user` | Users, roles, orgs, departments |
| Station | `module/station` | Monitoring station CRUD and type/location metadata |
| Sensor | `module/sensor` | Sensor device records, status, heartbeat |
| Observation | `module/observation` | Time-series observation query and batch ingestion |
| Threshold | `module/threshold` | Alarm threshold rules |
| Alarm | `module/alarm` | Alarm query, ACK/close lifecycle, scheduled checks |
| Resource | `module/resource` | Emergency resources and dispatch records |
| AI proxy | `module/ai` | Flood AI query, SSE, plans, conversations, knowledge base proxy |
| AI assessment | `module/aiassessment` | Persisted AI assessment records |
| Audit | `module/audit` | Audit log query |

## Configuration

Main configuration lives in:

- `src/main/resources/application.yml`
- `src/main/resources/application-dev.yml`
- `src/main/resources/application-prod.yml`

Important environment variables:

| Variable | Purpose | Default |
| --- | --- | --- |
| `SPRING_DATASOURCE_URL` | PostgreSQL JDBC URL | value from profile/config |
| `SPRING_DATASOURCE_USERNAME` | Database user | value from profile/config |
| `SPRING_DATASOURCE_PASSWORD` | Database password | value from profile/config |
| `SPRING_DATA_REDIS_HOST` | Redis host | value from profile/config |
| `SPRING_DATA_REDIS_PASSWORD` | Redis password | value from profile/config |
| `ADMIN_PASSWORD` | Initial admin password | `Admin@123456` |
| `JWT_SECRET` | JWT signing secret | development secret in config |
| `AI_SERVICE_URL` | Python AI service URL | `http://localhost:8100` |

For production, always override `ADMIN_PASSWORD`, `JWT_SECRET`, database credentials, and Redis credentials.

## Database Migrations

Flyway runs migrations from `src/main/resources/db/migration`.

Current migrations:

| File | Purpose |
| --- | --- |
| `V1__water_info_schema.sql` | Core water domain schema |
| `V2__user_access_control.sql` | User, role, permission tables |
| `V3__legacy_public_compat.sql` | Legacy public schema compatibility |
| `V4__legacy_public_seed_test_data.sql` | Legacy/demo seed data |
| `V5__performance_indexes.sql` | Performance indexes |
| `V7__cuiping_lake_demo_data.sql` | Cuiping Lake demo data |
| `V8__rag_knowledge_base.sql` | RAG knowledge-base tables |
| `V9__rag_embedding_dimension_fix.sql` | RAG embedding dimension adjustment |
| `V10__scheduled_risk_monitoring.sql` | Scheduled risk-monitoring support |
| `V11__resource_management.sql` | Resource and dispatch tables |

There is no `V6`; keep the historical gap and add future migrations with the next unused version.

## Local Development

### Prerequisites

- Java 17+
- Maven 3.8+
- PostgreSQL 15+
- Redis 7+
- Docker, if running Testcontainers-based tests

### Database

```sql
CREATE DATABASE water_info;
```

Flyway will apply migrations on application startup. If you need to run SQL manually:

```bash
psql -U postgres -d water_info -f src/main/resources/db/migration/V1__water_info_schema.sql
psql -U postgres -d water_info -f src/main/resources/db/migration/V2__user_access_control.sql
```

Prefer automatic Flyway execution for the full migration chain.

### Build and Run

```bash
mvn clean compile
mvn spring-boot:run -Dspring-boot.run.profiles=dev
```

Package:

```bash
mvn clean package -DskipTests
java -jar target/water-info-platform-1.0.0-SNAPSHOT.jar
```

API docs:

- Swagger UI: `http://localhost:8080/swagger-ui.html`
- Knife4j: `http://localhost:8080/doc.html`
- OpenAPI JSON: `http://localhost:8080/v3/api-docs`

## Authentication

Login:

```bash
curl -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"Admin@123456"}'
```

Use the returned access token:

```bash
curl http://localhost:8080/api/v1/stations \
  -H "Authorization: Bearer <access-token>"
```

## Main Endpoints

### Platform APIs

| Area | Endpoints |
| --- | --- |
| Auth | `POST /api/v1/auth/login`, `GET /api/v1/auth/me`, `POST /api/v1/auth/logout` |
| Users | `GET/POST /api/v1/users`, `GET/PUT/DELETE /api/v1/users/{id}` |
| Roles | `GET /api/v1/roles`, `GET /api/v1/roles/{id}` |
| Orgs/Depts | `GET/POST/PUT/DELETE /api/v1/orgs`, `GET/POST/PUT/DELETE /api/v1/depts` |
| Stations | `GET/POST /api/v1/stations`, `GET/PUT/DELETE /api/v1/stations/{id}` |
| Sensors | `GET/POST /api/v1/sensors`, `PUT /api/v1/sensors/{id}/status`, `PUT /api/v1/sensors/{id}/heartbeat` |
| Observations | `POST /api/v1/observations/batch`, `GET /api/v1/observations`, `GET /api/v1/observations/latest`, `POST /api/v1/observations/latest/batch` |
| Thresholds | `GET/POST /api/v1/threshold-rules`, `PUT /api/v1/threshold-rules/{id}/enable`, `PUT /api/v1/threshold-rules/{id}/disable` |
| Alarms | `GET /api/v1/alarms`, `GET /api/v1/alarms/{id}`, `POST /api/v1/alarms/{id}/ack`, `POST /api/v1/alarms/{id}/close` |
| Resources | `GET/POST /api/v1/resources`, `GET /api/v1/resources/stats`, `GET /api/v1/resources/available` |
| Dispatches | `GET/POST /api/v1/resource-dispatches`, `PATCH /api/v1/resource-dispatches/{id}/status` |
| Audit | `GET /api/v1/audit-logs` |
| AI assessments | `GET/POST /api/v1/ai-assessments` |

### AI Proxy APIs

The Java service proxies AI traffic to `AI_SERVICE_URL`.

| Area | Endpoints |
| --- | --- |
| Flood query | `POST /api/v1/flood/query`, `POST /api/v1/flood/query/stream` |
| Plans | `GET /api/v1/plans`, `GET /api/v1/plans/{id}`, `POST /api/v1/plans/{id}/execute` |
| Sessions | `GET /api/v1/sessions/{id}` |
| Conversations | `GET/POST /api/v1/conversations`, `GET/PATCH/DELETE /api/v1/conversations/{sessionId}`, `GET /api/v1/conversations/{sessionId}/messages` |
| Knowledge base | `POST /api/v1/kb/documents`, `GET /api/v1/kb/documents`, `GET /api/v1/kb/documents/{id}`, `DELETE /api/v1/kb/documents/{id}`, `POST /api/v1/kb/documents/{id}/reindex`, `POST /api/v1/kb/search`, `GET /api/v1/kb/stats` |

## Alarm Lifecycle

```text
OPEN -> ACK -> CLOSED
OPEN --------> CLOSED
```

Invalid transitions, such as reopening a closed alarm, are rejected by service-layer validation.

## Role Permissions

| Capability | ADMIN | OPERATOR | VIEWER |
| --- | --- | --- | --- |
| User/org/department management | Full | No | No |
| Station/sensor management | Full | Create/update/read | Read |
| Observation write | Yes | Yes | No |
| Observation read | Yes | Yes | Yes |
| Threshold management | Full | Create/update/read | Read |
| Alarm ACK/close | Yes | Yes | No |
| Resource and dispatch management | Full | Create/update/read | Read |
| AI query and plan read | Yes | Yes | Yes |
| Knowledge document upload/delete | Yes | No | No |
| Audit log read | Yes | Yes | No |

## WebSocket and Streaming

- Alarm WebSocket: `ws://localhost:8080/ws/alarms`
- AI flood-query SSE: `POST /api/v1/flood/query/stream`

The Nginx config disables buffering for SSE and forwards WebSocket upgrade headers.

## Testing

```bash
mvn test
mvn test -Dtest=StationServiceTest
mvn test -Dtest=StationServiceTest#shouldCreateStationSuccessfully
```

Some tests use Testcontainers and require Docker.

## Docker

The root `docker-compose.yml` builds this service as `platform` and injects production profile settings:

```bash
docker-compose build platform
docker-compose up -d postgres redis platform
docker-compose logs -f platform
```

## Security Notes

1. Change the default admin password after first startup.
2. Use a strong JWT secret in every non-local environment.
3. Keep production CORS, rate-limit, and HTTPS settings restrictive.
4. Do not expose Swagger/Knife4j publicly unless access is controlled.
5. Keep AI knowledge-base write endpoints administrator-only.
