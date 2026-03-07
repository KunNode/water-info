# Water Information Management System - Base Platform

Water Information Management System (Base Platform) - A Spring Boot backend providing unified data and service foundation for multi-agent flood emergency response systems.

## Technology Stack

- **Java**: 17
- **Framework**: Spring Boot 3.2.x
- **ORM**: MyBatis-Plus 3.5.5
- **Database**: PostgreSQL 15+ (primary) / MySQL profile (requires dedicated SQL migrations)
- **Migration**: Flyway
- **Security**: Spring Security + JWT
- **API Documentation**: OpenAPI 3.0 / Swagger UI / Knife4j
- **Testing**: JUnit 5 + Testcontainers

## Features

- **User & Permission System**: User management, role-based access control (ADMIN/OPERATOR/VIEWER)
- **Station Management**: Monitoring station CRUD with location and type support
- **Sensor Management**: Sensor device management with heartbeat tracking
- **Observation Data**: Time series data batch upload (up to 5000 records per batch)
- **Threshold Rules**: Configurable alert thresholds per station and metric
- **Alarm Management**: Automatic alarm generation with state machine (OPEN -> ACK -> CLOSED)
- **Audit Logging**: Comprehensive audit trail for critical operations

## Quick Start

### Prerequisites

- Java 17+
- Maven 3.8+
- PostgreSQL 15+ (or MySQL 8+)
- Docker (optional, for Testcontainers)

### 1. Database Setup

Create a PostgreSQL database:

```sql
CREATE DATABASE water_info;
```

### 1.1 Migration Notes (Two Files Only)

Current repository status:
- Application Flyway path: `src/main/resources/db/migration`
- Active migration files:
  - `V1__water_info_schema.sql` (water info domain)
  - `V2__user_access_control.sql` (user/role/permission domain)

If you want the latest reviewed schema in PostgreSQL, run:

```bash
psql -U postgres -d water_info -f src/main/resources/db/migration/V1__water_info_schema.sql
psql -U postgres -d water_info -f src/main/resources/db/migration/V2__user_access_control.sql
```

Data guardrails (scope consistency, metric range, latitude/longitude range, NULL-sensitive scope uniqueness) are already merged into these two files.

### 2. Configuration

Edit `src/main/resources/application.yml`:

```yaml
spring:
  datasource:
    url: jdbc:postgresql://localhost:5432/water_info
    username: postgres
    password: your_password

app:
  admin:
    password: YourSecurePassword123!  # Change this!
```

Or use environment variables:

```bash
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=water_info
export DB_USERNAME=postgres
export DB_PASSWORD=your_password
export ADMIN_PASSWORD=YourSecurePassword123!
```

### 3. Build & Run

```bash
# Build
mvn clean package -DskipTests

# Run
mvn spring-boot:run

# Or run the JAR
java -jar target/water-info-platform-1.0.0-SNAPSHOT.jar
```

### 4. Access API Docs

Open one of the following in your browser:
- Swagger UI: http://localhost:8080/swagger-ui.html
- Knife4j UI: http://localhost:8080/doc.html

### 5. Login & Get Token

```bash
# Login
curl -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "Admin@123456"}'

# Response:
{
  "code": 200,
  "message": "success",
  "data": {
    "accessToken": "eyJhbG...",
    "tokenType": "Bearer",
    "expiresIn": 86400,
    "user": {
      "id": "...",
      "username": "admin",
      "roles": ["ADMIN"]
    }
  }
}
```

### 6. Use the Token

Add the token to the Authorization header:

```bash
curl -X GET http://localhost:8080/api/v1/stations \
  -H "Authorization: Bearer eyJhbG..."
```

## API Examples

### Batch Upload Observations

```bash
curl -X POST http://localhost:8080/api/v1/observations/batch \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "requestId": "batch-001",
    "observations": [
      {
        "stationId": "STATION_UUID",
        "metricType": "WATER_LEVEL",
        "value": 12.5,
        "unit": "m",
        "observedAt": "2024-01-15T10:30:00",
        "qualityFlag": "GOOD",
        "source": "sensor-001"
      }
    ]
  }'
```

### Create Station

```bash
curl -X POST http://localhost:8080/api/v1/stations \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "code": "STN001",
    "name": "Test Station",
    "type": "WATER_LEVEL",
    "adminRegion": "Region A",
    "lat": 30.123456,
    "lon": 120.654321
  }'
```

### Create Threshold Rule

```bash
curl -X POST http://localhost:8080/api/v1/threshold-rules \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "stationId": "STATION_UUID",
    "metricType": "WATER_LEVEL",
    "level": "WARNING",
    "thresholdValue": 10.0
  }'
```

### Acknowledge Alarm

```bash
curl -X POST http://localhost:8080/api/v1/alarms/{alarmId}/ack \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Running Tests

```bash
# Run all tests (requires Docker for Testcontainers)
mvn test

# Skip tests
mvn package -DskipTests
```

## API Endpoints

### Authentication
- `POST /api/v1/auth/login` - Login and get JWT token
- `GET /api/v1/auth/me` - Get current user info
- `POST /api/v1/auth/logout` - Logout

### User Management (ADMIN)
- `POST /api/v1/users` - Create user
- `GET /api/v1/users` - List users
- `GET /api/v1/users/{id}` - Get user
- `PUT /api/v1/users/{id}` - Update user
- `PUT /api/v1/users/{id}/password` - Change password
- `PUT /api/v1/users/{id}/roles` - Set roles
- `DELETE /api/v1/users/{id}` - Delete user

### Stations
- `POST /api/v1/stations` - Create station
- `GET /api/v1/stations` - List stations
- `GET /api/v1/stations/{id}` - Get station
- `PUT /api/v1/stations/{id}` - Update station
- `DELETE /api/v1/stations/{id}` - Delete station

### Sensors
- `POST /api/v1/sensors` - Create sensor
- `GET /api/v1/sensors` - List sensors
- `PUT /api/v1/sensors/{id}/heartbeat` - Update heartbeat

### Observations
- `POST /api/v1/observations/batch` - Batch upload (1-5000 records)
- `GET /api/v1/observations` - Query observations
- `GET /api/v1/observations/latest` - Get latest observation

### Threshold Rules
- `POST /api/v1/threshold-rules` - Create rule
- `GET /api/v1/threshold-rules` - List rules
- `PUT /api/v1/threshold-rules/{id}/enable` - Enable rule
- `PUT /api/v1/threshold-rules/{id}/disable` - Disable rule

### Alarms
- `GET /api/v1/alarms` - List alarms
- `POST /api/v1/alarms/{id}/ack` - Acknowledge alarm
- `POST /api/v1/alarms/{id}/close` - Close alarm

### Audit Logs
- `GET /api/v1/audit-logs` - Query audit logs

## Alarm State Machine

```
                    +-----------+
                    |   OPEN    |
                    +-----------+
                          |
           +--------------+--------------+
           |                             |
           v                             v
     +-----------+                 +-----------+
     |    ACK    |---------------->|  CLOSED   |
     +-----------+                 +-----------+

Valid transitions:
- OPEN -> ACK (acknowledge)
- ACK -> CLOSED (close)
- OPEN -> CLOSED (close without ack)

Invalid transitions:
- ACK -> OPEN
- CLOSED -> any
```

## Role Permissions

| Operation | ADMIN | OPERATOR | VIEWER |
|-----------|-------|----------|--------|
| User CRUD | Yes | No | No |
| Station CRUD | Yes | Yes | Read |
| Sensor CRUD | Yes | Yes | Read |
| Observation Write | Yes | Yes | No |
| Observation Read | Yes | Yes | Yes |
| Threshold CRUD | Yes | Yes | Read |
| Alarm ACK/Close | Yes | Yes | No |
| Alarm Read | Yes | Yes | Yes |
| Audit Log Read | Yes | Yes | No |

## MySQL Support

To use MySQL instead of PostgreSQL:

1. Create MySQL database:
```sql
CREATE DATABASE water_info CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

2. Create MySQL migration file at `src/main/resources/db/migration/mysql/V1__init.sql`
   (Note: the PostgreSQL `V1/V2` scripts use PostgreSQL-specific features such as `JSONB`, partial indexes, and `UUID[]`. They are not directly portable to MySQL.)

3. Run with MySQL profile:
```bash
mvn spring-boot:run -Dspring.profiles.active=mysql
```

## Observation Time Series Partitioning (Optional)

For high-volume observation data, consider:
- PostgreSQL: Use native table partitioning by month
- TimescaleDB: Use hypertables for automatic partitioning

Example partition setup (not included in V1):
```sql
-- Convert to partitioned table
CREATE TABLE observation_new (LIKE observation INCLUDING ALL)
PARTITION BY RANGE (observed_at);

-- Create monthly partitions
CREATE TABLE observation_2024_01 PARTITION OF observation_new
FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
```

## Security Notes

1. **Change default admin password immediately after first deployment**
2. **Use strong JWT secret in production** (at least 256 bits)
3. **Enable HTTPS in production**
4. **Review and restrict CORS settings for production**

## License

Proprietary - All Rights Reserved
