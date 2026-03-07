import dayjs from 'dayjs'

export function formatDate(date: string | Date, fmt = 'YYYY-MM-DD HH:mm:ss'): string {
  if (!date) return '-'
  return dayjs(date).format(fmt)
}

export function formatShortDate(date: string | Date): string {
  return formatDate(date, 'YYYY-MM-DD')
}

export function formatTime(date: string | Date): string {
  return formatDate(date, 'HH:mm:ss')
}

export function formatNumber(num: number | null | undefined, digits = 2): string {
  if (num === null || num === undefined) return '-'
  return Number(num).toFixed(digits)
}

export function formatPercent(num: number, digits = 1): string {
  return `${(num * 100).toFixed(digits)}%`
}

// Map station type to Chinese label
export const stationTypeMap: Record<string, string> = {
  WATER_LEVEL: '水位站',
  RAIN_GAUGE: '雨量站',
  FLOW: '流量站',
  RESERVOIR: '水库站',
  GATE: '闸门站',
  PUMP_STATION: '泵站',
}

export const metricTypeMap: Record<string, string> = {
  WATER_LEVEL: '水位',
  RAINFALL: '降雨量',
  FLOW: '流量',
}

export const alarmLevelMap: Record<string, { label: string; color: string }> = {
  CRITICAL: { label: '特急', color: '#F56C6C' },
  HIGH: { label: '紧急', color: '#E6A23C' },
  MEDIUM: { label: '一般', color: '#409EFF' },
  LOW: { label: '提示', color: '#909399' },
}

export const alarmStatusMap: Record<string, { label: string; type: string }> = {
  OPEN: { label: '待处理', type: 'danger' },
  ACK: { label: '已确认', type: 'warning' },
  CLOSED: { label: '已关闭', type: 'info' },
}

export const riskLevelMap: Record<string, { label: string; color: string }> = {
  none: { label: '无风险', color: '#67C23A' },
  low: { label: '低风险', color: '#409EFF' },
  moderate: { label: '中等风险', color: '#E6A23C' },
  high: { label: '高风险', color: '#F56C6C' },
  critical: { label: '极高风险', color: '#911' },
}
