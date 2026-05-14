# Database Seed Scripts

`db/migration` is reserved for schema, index, and structural changes that should run automatically with Flyway.

This directory contains optional data scripts for local demos or test datasets. They are not included in the default Flyway migration path.

Run one manually when demo data is needed, for example:

```bash
docker compose exec -T postgres psql -U root -d water_info < water-info-platform/src/main/resources/db/seed/cuiping_lake_demo_data.sql
```

To restore only the original station catalog and sensor configuration:

```bash
docker compose exec -T postgres psql -U root -d water_info < water-info-platform/src/main/resources/db/seed/station_baseline.sql
```

To clear runtime/demo data while keeping table structure:

```bash
docker compose exec -T postgres psql -U root -d water_info < water-info-platform/src/main/resources/db/maintenance/clear_data.sql
```

To stream one hour of demo observations, one batch per minute:

```bash
scripts/demo/stream_observations_1h.sh
```
