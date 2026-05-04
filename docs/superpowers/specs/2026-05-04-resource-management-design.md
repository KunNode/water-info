# Resource Management Module Design

Date: 2026-05-04

## Overview

Add a resource management module to the Smart Water Management system, enabling administrators to manage emergency resources (materials, personnel, vehicles) through the admin dashboard. The AI service's ResourceDispatcher agent will query real resource inventory instead of generating hypothetical allocations, and can create dispatch orders that automatically update inventory.

## Motivation

Currently, resource data is ephemeral — it exists only in the AI service's in-memory LangGraph state. The ResourceDispatcher agent relies entirely on the LLM to generate resource allocations with no awareness of actual inventory. This design connects the AI to a persistent resource registry, making emergency resource dispatch data-driven and auditable.

## Architecture

```
┌─────────────────┐     ┌──────────────────────┐     ┌──────────────────────┐
│  Admin Frontend  │────▶│  Spring Boot Platform │◀────│   FastAPI AI Service  │
│  Resource CRUD   │     │  /api/v1/resources    │     │  ResourceDispatcher   │
│  Dispatch View   │     │  /api/v1/dispatches   │     │  + resource_tools     │
└─────────────────┘     └──────────┬─────────────┘     └──────────────────────┘
                                    │
                              ┌─────▼─────┐
                              │ PostgreSQL │
                              │ resource   │
                              │ dispatch   │
                              └───────────┘
```

## Database Schema

### Table: `resource`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, default `gen_random_uuid()` | Primary key |
| `type` | VARCHAR(20) | NOT NULL | `MATERIAL` / `PERSONNEL` / `VEHICLE` |
| `name` | VARCHAR(100) | NOT NULL | Resource name |
| `quantity` | INTEGER | NOT NULL, >= 0 | Available quantity |
| `unit` | VARCHAR(20) | NOT NULL | Unit of measure (个/人/辆/台) |
| `location` | VARCHAR(200) | NOT NULL | Storage/station location |
| `status` | VARCHAR(20) | NOT NULL, default `AVAILABLE` | `AVAILABLE` / `IN_USE` / `MAINTENANCE` / `DEPLETED` |
| `attributes` | JSONB | default `{}` | Type-specific attributes |
| `description` | TEXT | | Notes |
| `created_at` | TIMESTAMP | NOT NULL, default `now()` | |
| `updated_at` | TIMESTAMP | NOT NULL, default `now()` | |
| `deleted` | BOOLEAN | NOT NULL, default `false` | Soft delete |

**`attributes` JSONB schemas by type:**

- MATERIAL: `{"brand": "string", "spec": "string", "expiry_date": "YYYY-MM-DD", "min_stock_alert": 100}`
- PERSONNEL: `{"team_size": 12, "skills": ["string"], "leader": "string", "contact": "string"}`
- VEHICLE: `{"plate_number": "string", "capacity": "string", "fuel_type": "string"}`

**Indexes:** `type`, `status`, `name` (btree), `attributes` (gin for JSONB queries).

### Table: `resource_dispatch`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, default `gen_random_uuid()` | Primary key |
| `resource_id` | UUID | FK → `resource.id`, NOT NULL | Dispatched resource |
| `plan_id` | VARCHAR(50) | | Associated emergency plan ID (nullable for manual dispatch) |
| `quantity` | INTEGER | NOT NULL, > 0 | Dispatched quantity |
| `from_location` | VARCHAR(200) | NOT NULL | Source location |
| `to_location` | VARCHAR(200) | NOT NULL | Destination |
| `status` | VARCHAR(20) | NOT NULL, default `PENDING` | `PENDING` / `DISPATCHED` / `ARRIVED` / `RETURNED` / `CANCELLED` |
| `dispatched_at` | TIMESTAMP | | Dispatch timestamp |
| `arrived_at` | TIMESTAMP | | Arrival timestamp |
| `returned_at` | TIMESTAMP | | Return timestamp |
| `operator` | VARCHAR(50) | | Who created the dispatch |
| `source` | VARCHAR(20) | NOT NULL, default `MANUAL` | `AI` / `MANUAL` |
| `notes` | TEXT | | Remarks |
| `created_at` | TIMESTAMP | NOT NULL, default `now()` | |
| `updated_at` | TIMESTAMP | NOT NULL, default `now()` | |

**Indexes:** `resource_id`, `status`, `plan_id`, `dispatched_at`.

**Inventory linkage:** When a dispatch order is created with status `PENDING` or `DISPATCHED`, the resource's `quantity` is decremented by the dispatch quantity. When status becomes `RETURNED` or `CANCELLED`, the quantity is restored. This is handled in the `ResourceDispatchService.create()` and `updateStatus()` methods.

## Backend API (water-info-platform)

New module: `module/resource/` following the existing `entity → dto → vo → mapper → service → controller` pattern.

### Resource endpoints (`/api/v1/resources`)

| Method | Path | Description | Auth |
|---|---|---|---|
| GET | `/api/v1/resources` | Paginated list with filters (type, status, keyword) | VIEWER+ |
| GET | `/api/v1/resources/{id}` | Resource detail | VIEWER+ |
| POST | `/api/v1/resources` | Create resource | OPERATOR+ |
| PUT | `/api/v1/resources/{id}` | Update resource | OPERATOR+ |
| DELETE | `/api/v1/resources/{id}` | Soft delete | ADMIN |
| GET | `/api/v1/resources/stats` | Aggregate stats by type/status | VIEWER+ |
| GET | `/api/v1/resources/available` | Available resources for AI (status=AVAILABLE, quantity>0) | Internal |

### Dispatch endpoints (`/api/v1/resource-dispatches`)

| Method | Path | Description | Auth |
|---|---|---|---|
| GET | `/api/v1/resource-dispatches` | Paginated list with filters | VIEWER+ |
| GET | `/api/v1/resource-dispatches/{id}` | Dispatch detail | VIEWER+ |
| POST | `/api/v1/resource-dispatches` | Create dispatch order | OPERATOR+ |
| PATCH | `/api/v1/resource-dispatches/{id}/status` | Update dispatch status | OPERATOR+ |

Response format: existing `ApiResponse<T>` wrapper with `traceId`, `timestamp`, `pagination`.

## AI Service Integration (water-info-ai)

### New file: `app/tools/resource_tools.py`

Two `@tool`-decorated async functions:

**`query_available_resources(resource_type: str = "", location: str = "")`**
- Calls `PlatformClient.get("/api/v1/resources/available", params={...})`
- Returns list of available resources with id, name, type, quantity, location, attributes

**`create_dispatch_orders(dispatches: list[dict])`**
- Each dict: `{resource_id, quantity, from_location, to_location, plan_id}`
- Calls `PlatformClient.post("/api/v1/resource-dispatches", body=...)` for each
- Returns list of created dispatch records with IDs

### Modified: `app/agents/resource_dispatcher.py`

Current flow: LLM generates resource JSON from thin air.

New flow:
1. Read `emergency_plan` from state for context
2. Call `query_available_resources` tool to get real inventory
3. LLM generates dispatch plan based on actual available resources
4. Call `create_dispatch_orders` tool to persist dispatches
5. Output `resource_plan` with real `resource_id` and `dispatch_id`

### Modified: `app/state.py`

Extend `ResourceAllocation` dataclass:
- `resource_id: str | None = None` — linked resource ID
- `dispatch_id: str | None = None` — linked dispatch order ID

### Modified: `app/services/platform_client.py`

No structural changes needed — existing `get()` and `post()` methods are sufficient.

## Frontend (water-info-admin)

### Route structure

New top-level menu: "资源管理" (icon: Box)

| Route | Component | Title |
|---|---|---|
| `/resource/material` | `views/resource/material/index.vue` | 物资管理 |
| `/resource/personnel` | `views/resource/personnel/index.vue` | 人员管理 |
| `/resource/vehicle` | `views/resource/vehicle/index.vue` | 车辆设备 |
| `/resource/dispatch` | `views/resource/dispatch/index.vue` | 调度记录 |

### New files

- `src/api/resource.ts` — API functions for resource and dispatch CRUD
- `src/views/resource/material/index.vue` — Material list with table, filters, form dialog
- `src/views/resource/personnel/index.vue` — Personnel list
- `src/views/resource/vehicle/index.vue` — Vehicle list
- `src/views/resource/dispatch/index.vue` — Dispatch records list
- `src/views/resource/components/ResourceForm.vue` — Shared resource form dialog (type-aware: shows relevant `attributes` fields based on type)
- `src/views/resource/components/DispatchForm.vue` — Dispatch order form dialog

### UI details

- Resource list uses a shared component with type-based tab switching (物资/人员/车辆)
- Status badges: AVAILABLE(green), IN_USE(blue), MAINTENANCE(orange), DEPLETED(red)
- Low-stock alert: highlight rows where `quantity < attributes.min_stock_alert`
- Dispatch status flow: PENDING → DISPATCHED → ARRIVED → RETURNED (with CANCELLED as alternative)
- Dispatch records show `source` column: AI-generated vs manual

## Data Flow: End-to-End

```
1. Admin adds resources via /resource/* pages → POST /api/v1/resources
2. Flood emergency triggers AI workflow
3. Supervisor routes to resource_dispatcher
4. resource_dispatcher calls query_available_resources tool
   → PlatformClient.get("/api/v1/resources/available")
   → Returns real inventory
5. LLM generates dispatch plan based on actual stock
6. resource_dispatcher calls create_dispatch_orders tool
   → PlatformClient.post("/api/v1/resource-dispatches")
   → Backend creates dispatch records + decrements resource quantities
7. resource_plan in state now has real resource_id and dispatch_id
8. Frontend shows dispatches in /resource/dispatch page with source=AI
9. When dispatch completes, operator updates status to ARRIVED/RETURNED
   → RETURNED restores resource quantity
```

## Implementation Order

1. **Database migration** — V11 schema (resource + resource_dispatch tables)
2. **Platform module** — entity, dto, vo, mapper, service, controller for resource and dispatch
3. **Frontend resource pages** — API layer, components, route registration
4. **AI resource tools** — resource_tools.py with query and create functions
5. **AI agent refactor** — update ResourceDispatcher to use tools
6. **Integration test** — end-to-end flow verification
