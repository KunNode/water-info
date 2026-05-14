-- Clear runtime/demo data while preserving schema and migration metadata.
-- The platform startup initializer will recreate default roles/admin if needed.

DO $$
DECLARE
  table_list text;
BEGIN
  SELECT string_agg(format('%I.%I', schemaname, tablename), ', ')
    INTO table_list
  FROM pg_tables
  WHERE schemaname IN ('public', 'water_info')
    AND tablename NOT IN (
      'flyway_schema_history',
      'checkpoint_migrations',
      'store_migrations',
      'sys_role',
      'station',
      'sensor'
    );

  IF table_list IS NOT NULL THEN
    EXECUTE 'TRUNCATE TABLE ' || table_list || ' RESTART IDENTITY CASCADE';
  END IF;
END $$;

INSERT INTO public.sys_role (id, code, name, description)
SELECT gen_random_uuid()::text, 'ADMIN', 'Administrator', 'Full system access'
WHERE NOT EXISTS (SELECT 1 FROM public.sys_role WHERE code = 'ADMIN');

INSERT INTO public.sys_role (id, code, name, description)
SELECT gen_random_uuid()::text, 'OPERATOR', 'Operator', 'Can manage data, alarms, and resources'
WHERE NOT EXISTS (SELECT 1 FROM public.sys_role WHERE code = 'OPERATOR');

INSERT INTO public.sys_role (id, code, name, description)
SELECT gen_random_uuid()::text, 'VIEWER', 'Viewer', 'Read-only access'
WHERE NOT EXISTS (SELECT 1 FROM public.sys_role WHERE code = 'VIEWER');
