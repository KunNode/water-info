const SENSITIVE_KEY_PATTERN = /(token|secret|password|authorization|cookie|credential|key|phone|mobile|email|idCard|身份证|手机号)/i

const TOOL_COPY: Record<string, { running: string; success: string; fallback: string }> = {
  query_water_level: {
    running: '正在查询实时水情数据...',
    success: '已获取实时水情数据',
    fallback: '实时水情查询失败，正在尝试备用数据源',
  },
  get_water_levels: {
    running: '正在查询实时水情数据...',
    success: '已获取实时水情数据',
    fallback: '实时水情查询失败，正在尝试备用数据源',
  },
  query_rainfall: {
    running: '正在查询降雨监测数据...',
    success: '已获取降雨监测数据',
    fallback: '降雨数据查询失败，正在使用最近一次监测结果',
  },
  get_rainfall_data: {
    running: '正在查询降雨监测数据...',
    success: '已获取降雨监测数据',
    fallback: '降雨数据查询失败，正在使用最近一次监测结果',
  },
  query_active_alarms: {
    running: '正在核查当前预警与告警...',
    success: '已核查当前预警与告警',
    fallback: '告警查询失败，正在根据当前水情继续研判',
  },
  assess_flood_risk: {
    running: '正在评估洪涝风险等级...',
    success: '已完成洪涝风险评估',
    fallback: '风险评估遇到异常，正在使用保守规则继续分析',
  },
  generate_emergency_plan: {
    running: '正在生成应急处置建议...',
    success: '已形成应急处置建议',
    fallback: '预案生成遇到异常，正在输出可执行的简化建议',
  },
  dispatch_resources: {
    running: '正在匹配可调度队伍与物资...',
    success: '已匹配可调度队伍与物资',
    fallback: '资源匹配暂不可用，正在给出人工调度建议',
  },
  send_notification: {
    running: '正在整理预警通知方案...',
    success: '已整理预警通知方案',
    fallback: '通知方案生成失败，正在保留核心处置结论',
  },
  search_knowledge_base: {
    running: '正在检索知识库与历史预案...',
    success: '已检索知识库与历史预案',
    fallback: '知识库检索失败，正在根据实时态势继续分析',
  },
}

export function mapToolCallTitle(toolName?: string, phase: 'running' | 'success' | 'fallback' = 'running') {
  if (!toolName) return phase === 'fallback' ? '工具调用失败，正在尝试降级处理' : '正在调用工具...'
  const normalized = toolName.trim()
  const copy = TOOL_COPY[normalized]
  if (copy) return copy[phase]

  if (/rain|雨/i.test(normalized)) return phase === 'fallback' ? '降雨数据查询失败，正在尝试降级处理' : '正在查询降雨监测数据...'
  if (/water|level|水位|水情/i.test(normalized)) return phase === 'fallback' ? '水情数据查询失败，正在尝试降级处理' : '正在查询实时水情数据...'
  if (/alarm|warning|告警|预警/i.test(normalized)) return phase === 'fallback' ? '预警查询失败，正在尝试降级处理' : '正在核查当前预警与告警...'
  if (/risk|风险/i.test(normalized)) return phase === 'fallback' ? '风险评估遇到异常，正在降级分析' : '正在评估洪涝风险等级...'
  if (/plan|预案/i.test(normalized)) return phase === 'fallback' ? '预案生成遇到异常，正在输出简化建议' : '正在生成应急处置建议...'

  return phase === 'fallback' ? '工具调用失败，正在尝试降级处理' : '正在分析相关数据...'
}

export function redactSensitive(value: unknown): unknown {
  if (Array.isArray(value)) return value.slice(0, 8).map(redactSensitive)
  if (!value || typeof value !== 'object') return value

  return Object.entries(value as Record<string, unknown>).reduce<Record<string, unknown>>((acc, [key, entry]) => {
    acc[key] = SENSITIVE_KEY_PATTERN.test(key) ? '***' : redactSensitive(entry)
    return acc
  }, {})
}

export function summarizeToolResult(toolName: string | undefined, result: unknown, fallback?: string) {
  if (fallback?.trim()) return fallback.trim()
  if (!result) return toolName ? mapToolCallTitle(toolName, 'success') : '已完成数据分析'

  const safeResult = redactSensitive(result)
  if (typeof safeResult === 'string') return truncate(safeResult)
  if (Array.isArray(safeResult)) return summarizeArrayResult(toolName, safeResult)
  if (typeof safeResult === 'object') return summarizeObjectResult(toolName, safeResult as Record<string, unknown>)

  return truncate(String(safeResult))
}

function summarizeArrayResult(toolName: string | undefined, rows: unknown[]) {
  if (!rows.length) return '未发现需要重点关注的数据'

  const head = rows[0]
  const count = rows.length
  if (toolName && /alarm|warning|告警|预警/i.test(toolName)) return `发现 ${count} 条预警/告警记录，已纳入研判`
  if (toolName && /rain|雨/i.test(toolName)) return `获取 ${count} 条降雨监测记录，已用于趋势判断`
  if (toolName && /water|level|水位|水情/i.test(toolName)) return `获取 ${count} 条水情监测记录，已用于风险评估`

  if (head && typeof head === 'object') {
    const keys = Object.keys(head as Record<string, unknown>).slice(0, 3)
    return `返回 ${count} 条结果，关键字段：${keys.join('、') || '已脱敏'}`
  }
  return `返回 ${count} 条结果`
}

function summarizeObjectResult(toolName: string | undefined, value: Record<string, unknown>) {
  const count = pickNumber(value, ['count', 'total', 'size'])
  const level = pickString(value, ['risk_level', 'level', 'status'])
  const summary = pickString(value, ['summary', 'message', 'description'])

  if (summary) return truncate(summary)
  if (level && count != null) return `状态为 ${level}，涉及 ${count} 条关键数据`
  if (level) return `状态为 ${level}，已纳入最终研判`
  if (count != null) return `返回 ${count} 条结果，已完成摘要整理`

  const keys = Object.keys(value).slice(0, 4)
  if (keys.length) return `已获取 ${keys.join('、')} 等信息`
  return toolName ? mapToolCallTitle(toolName, 'success') : '已完成数据分析'
}

function pickString(value: Record<string, unknown>, keys: string[]) {
  for (const key of keys) {
    const entry = value[key]
    if (typeof entry === 'string' && entry.trim()) return entry.trim()
  }
  return ''
}

function pickNumber(value: Record<string, unknown>, keys: string[]) {
  for (const key of keys) {
    const entry = value[key]
    if (typeof entry === 'number') return entry
  }
  return null
}

function truncate(value: string, max = 120) {
  const trimmed = value.replace(/\s+/g, ' ').trim()
  return trimmed.length > max ? `${trimmed.slice(0, max)}...` : trimmed
}

