import type { NewAgentStreamEvent } from '@/types/agentStream'

export const mockAgentThoughtChainEvents: NewAgentStreamEvent[] = [
  {
    type: 'message_start',
    messageId: 'msg_mock_001',
    sessionId: 'mock-session-001',
  },
  {
    type: 'thought_start',
    id: 'thought_intent',
    title: '正在理解指挥意图',
    content: '用户关注当前水情、风险等级和处置建议，需要先汇总实时监测与告警信息。',
  },
  {
    type: 'thought_delta',
    id: 'thought_intent',
    delta: ' 已将任务拆分为水情查询、风险研判和应急建议三部分。',
  },
  {
    type: 'thought_end',
    id: 'thought_intent',
    durationMs: 900,
  },
  {
    type: 'tool_start',
    id: 'tool_water_level',
    toolName: 'query_water_level',
    inputSummary: '查询翠屏湖及上游重点站点近 2 小时水位',
  },
  {
    type: 'tool_delta',
    id: 'tool_water_level',
    delta: '正在读取重点站水位曲线...',
  },
  {
    type: 'tool_result',
    id: 'tool_water_level',
    summary: '翠屏湖水位持续上涨，2 个上游站点超过警戒线',
  },
  {
    type: 'tool_end',
    id: 'tool_water_level',
    status: 'success',
    durationMs: 1280,
  },
  {
    type: 'tool_start',
    id: 'tool_alarm',
    toolName: 'query_active_alarms',
    inputSummary: '核查当前未关闭告警',
  },
  {
    type: 'tool_result',
    id: 'tool_alarm',
    data: [
      { level: 'HIGH', stationName: '翠屏湖', message: '水位超过警戒阈值' },
      { level: 'MEDIUM', stationName: '北溪雨量站', message: '小时雨强偏高' },
    ],
  },
  {
    type: 'tool_end',
    id: 'tool_alarm',
    status: 'success',
    durationMs: 820,
  },
  {
    type: 'thought_start',
    id: 'thought_risk',
    title: '正在综合研判风险',
    content: '水位上涨与降雨增强叠加，短时风险需要按高风险处置。',
  },
  {
    type: 'thought_end',
    id: 'thought_risk',
    durationMs: 700,
  },
  {
    type: 'answer_start',
  },
  {
    type: 'answer_delta',
    delta: '当前建议按**高风险**响应处置：\n\n',
  },
  {
    type: 'answer_delta',
    delta: '1. 对翠屏湖及上游站点保持 15 分钟滚动监测；\n2. 通知巡查队伍前往低洼易涝点；\n3. 准备开启预案中的人员转移和物资前置流程。',
  },
  {
    type: 'answer_end',
    durationMs: 2100,
  },
]

export function toMockSSELines(events = mockAgentThoughtChainEvents) {
  return events.map(event => `event: ${event.type}\ndata: ${JSON.stringify(event)}\n\n`).join('')
}

