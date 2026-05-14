-- Align sensor status values with the frontend sensor model.

BEGIN;

ALTER TABLE sensor DROP CONSTRAINT IF EXISTS sensor_status_check;

UPDATE sensor SET status = 'ONLINE' WHERE status = 'ACTIVE';
UPDATE sensor SET status = 'OFFLINE' WHERE status = 'INACTIVE';

ALTER TABLE sensor
    ADD CONSTRAINT sensor_status_check
    CHECK (status IN ('ONLINE', 'OFFLINE', 'MAINTENANCE'));

ALTER TABLE sensor ALTER COLUMN status SET DEFAULT 'ONLINE';

COMMIT;
