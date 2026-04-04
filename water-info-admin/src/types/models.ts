// ─── Auth ───
export interface LoginRequest {
  username: string
  password: string
}

export interface LoginResponse {
  accessToken: string
  refreshToken: string
  tokenType: string
  expiresIn: number
  user: UserInfo
}

export interface UserInfo {
  id: string
  username: string
  realName: string
  orgId: string
  deptId: string
  roles: string[]
}

// ─── Station ───
export type StationType = 'WATER_LEVEL' | 'RAIN_GAUGE' | 'FLOW' | 'RESERVOIR' | 'GATE' | 'PUMP_STATION'
export type StationStatus = 'ACTIVE' | 'INACTIVE' | 'MAINTENANCE'

export interface Station {
  id: string
  code: string
  name: string
  type: StationType
  riverBasin: string
  adminRegion: string
  lat: number
  lon: number
  elevation: number
  status: StationStatus
  createdAt: string
  updatedAt: string
}

export interface CreateStationRequest {
  code: string
  name: string
  type: StationType
  riverBasin?: string
  adminRegion?: string
  lat?: number
  lon?: number
  elevation?: number
}

export interface UpdateStationRequest extends Partial<CreateStationRequest> {}

export interface StationQuery {
  page?: number
  size?: number
  type?: StationType
  adminRegion?: string
  status?: StationStatus
  keyword?: string
}

// ─── Sensor ───
export type SensorStatus = 'ONLINE' | 'OFFLINE' | 'MAINTENANCE'

export interface Sensor {
  id: string
  stationId: string
  stationCode: string
  stationName: string
  type: string
  unit: string
  samplingIntervalSec: number
  status: SensorStatus
  lastSeenAt: string
  meta: Record<string, any>
  createdAt: string
  updatedAt: string
}

export interface CreateSensorRequest {
  stationId: string
  type: string
  unit?: string
  samplingIntervalSec?: number
}

export interface SensorQuery {
  page?: number
  size?: number
  stationId?: string
  type?: string
  status?: SensorStatus
}

// ─── Observation ───
export type MetricType = 'WATER_LEVEL' | 'RAINFALL' | 'FLOW'
export type QualityFlag = 'GOOD' | 'FAIR' | 'SUSPECT' | 'MISSING'

export interface Observation {
  id: string
  stationId: string
  stationCode: string
  stationName: string
  metricType: MetricType
  value: number
  unit: string
  observedAt: string
  qualityFlag: QualityFlag
  source: string
  createdAt: string
}

export interface ObservationQuery {
  page?: number
  size?: number
  stationId?: string
  metricType?: MetricType
  start?: string
  end?: string
}

// ─── Alarm ───
export type AlarmLevel = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'
export type AlarmStatus = 'OPEN' | 'ACK' | 'CLOSED'

export interface Alarm {
  id: string
  stationId: string
  stationCode: string
  stationName: string
  metricType: string
  level: AlarmLevel
  startAt: string
  lastTriggerAt: string
  endAt: string | null
  status: AlarmStatus
  message: string
  acknowledgedBy: string | null
  acknowledgedByName: string | null
  acknowledgedAt: string | null
  closedBy: string | null
  closedByName: string | null
  closedAt: string | null
  createdAt: string
}

export interface AlarmQuery {
  page?: number
  size?: number
  stationId?: string
  metricType?: string
  level?: AlarmLevel
  status?: AlarmStatus
  start?: string
  end?: string
}

// ─── ThresholdRule ───
export interface ThresholdRule {
  id: string
  stationId: string
  stationCode: string
  stationName: string
  metricType: string
  level: AlarmLevel
  thresholdValue: number
  durationMin: number
  rateThreshold: number
  enabled: boolean
  createdAt: string
  updatedAt: string
}

export interface CreateThresholdRuleRequest {
  stationId: string
  metricType: string
  level: AlarmLevel
  thresholdValue: number
  durationMin?: number
  rateThreshold?: number
}

export interface ThresholdRuleQuery {
  page?: number
  size?: number
  stationId?: string
  metricType?: string
  enabled?: boolean
}

// ─── User ───
export interface User {
  id: string
  username: string
  realName: string
  phone: string
  email: string
  orgId: string
  orgName: string
  deptId: string
  deptName: string
  status: string
  lastLoginAt: string
  createdAt: string
  roles: Role[]
}

export interface CreateUserRequest {
  username: string
  password: string
  realName?: string
  phone?: string
  email?: string
  orgId?: string
  deptId?: string
}

export interface UserQuery {
  page?: number
  size?: number
  orgId?: string
  deptId?: string
  status?: string
  keyword?: string
}

// ─── Role ───
export interface Role {
  id: string
  code: string
  name: string
  description: string
  createdAt: string
  updatedAt: string
}

// ─── Org ───
export interface Org {
  id: string
  name: string
  code: string
  region: string
  createdAt: string
  updatedAt: string
}

export interface CreateOrgRequest {
  name: string
  code: string
  region?: string
}

// ─── Dept ───
export interface Dept {
  id: string
  orgId: string
  name: string
  parentId: string | null
  createdAt: string
  updatedAt: string
}

export interface CreateDeptRequest {
  orgId: string
  name: string
  parentId?: string
}

// ─── AuditLog ───
export interface AuditLog {
  id: string
  actorUserId: string
  actorUsername: string
  action: string
  targetType: string
  targetId: string
  detail: Record<string, any>
  ip: string
  userAgent: string
  createdAt: string
}

export interface AuditLogQuery {
  page?: number
  size?: number
  action?: string
  actorUserId?: string
  start?: string
  end?: string
}

// ─── AI / Flood Plan ───
export interface FloodQueryRequest {
  query: string
  sessionId?: string
}

export interface FloodPlan {
  id: string
  sessionId: string
  riskLevel: 'none' | 'low' | 'moderate' | 'high' | 'critical'
  summary: string
  actions: PlanAction[]
  resources: PlanResource[]
  notifications: PlanNotification[]
  status: 'draft' | 'approved' | 'executing' | 'completed'
  createdAt: string
  updatedAt: string
}

export interface PlanExecuteResult {
  planId: string
  status: string
  executedActions: number
  message: string
}

export interface FloodSession {
  sessionId: string
  plans: FloodPlan[]
  createdAt: string
}

export interface PlanAction {
  id: string
  description: string
  priority: string
  assignee: string
  status: string
}

export interface PlanResource {
  type: string
  name: string
  quantity: number
  location: string
}

export interface PlanNotification {
  channel: string
  target: string
  message: string
  status: string
}
