BEGIN;

INSERT INTO emergency_plan (
    plan_id,
    plan_name,
    risk_level,
    trigger_conditions,
    status,
    session_id,
    summary
) VALUES (
    'EP-TEST-20260331-001',
    'Demo Flood Response Plan',
    'high',
    'Water level above warning line and continuous rainfall in upstream area',
    'approved',
    'session-demo-20260331-001',
    'Demo flood response plan for the upstream river section with evacuation, pump deployment, and alert coordination.'
)
ON CONFLICT (plan_id) DO UPDATE SET
    plan_name = EXCLUDED.plan_name,
    risk_level = EXCLUDED.risk_level,
    trigger_conditions = EXCLUDED.trigger_conditions,
    status = EXCLUDED.status,
    session_id = EXCLUDED.session_id,
    summary = EXCLUDED.summary,
    updated_at = NOW();

DELETE FROM emergency_action WHERE plan_id = 'EP-TEST-20260331-001';
DELETE FROM resource_allocation WHERE plan_id = 'EP-TEST-20260331-001';
DELETE FROM notification_record WHERE plan_id = 'EP-TEST-20260331-001';

INSERT INTO emergency_action (
    plan_id,
    action_id,
    action_type,
    description,
    priority,
    responsible_dept,
    deadline_minutes,
    status
) VALUES
    (
        'EP-TEST-20260331-001',
        'ACT-001',
        'evacuation',
        'Open community evacuation points and notify at-risk residents within the low-lying block.',
        1,
        'Emergency Command Center',
        30,
        'pending'
    ),
    (
        'EP-TEST-20260331-001',
        'ACT-002',
        'drainage',
        'Deploy mobile pump trucks to the culvert crossing and clear drainage obstacles.',
        2,
        'Drainage Operations Team',
        45,
        'pending'
    ),
    (
        'EP-TEST-20260331-001',
        'ACT-003',
        'traffic_control',
        'Set temporary control on the riverside road and keep one emergency lane open.',
        3,
        'Traffic Coordination Team',
        60,
        'pending'
    );

INSERT INTO resource_allocation (
    plan_id,
    resource_type,
    resource_name,
    quantity,
    source_location,
    target_location,
    eta_minutes
) VALUES
    (
        'EP-TEST-20260331-001',
        'vehicle',
        'Mobile Pump Truck',
        2,
        'North Equipment Depot',
        'Riverside Culvert Crossing',
        25
    ),
    (
        'EP-TEST-20260331-001',
        'material',
        'Sandbag Pack',
        300,
        'Central Flood Warehouse',
        'Upstream River Section A',
        40
    );

INSERT INTO notification_record (
    plan_id,
    target,
    channel,
    content,
    status,
    sent_at
) VALUES
    (
        'EP-TEST-20260331-001',
        'Community Grid Leaders',
        'sms',
        'Activate local flood watch and guide residents to evacuation points.',
        'pending',
        NULL
    ),
    (
        'EP-TEST-20260331-001',
        'Drainage Duty Team',
        'radio',
        'Start pump deployment and report readiness every 15 minutes.',
        'pending',
        NULL
    );

COMMIT;
