export type AgentMessageStatus = 'thinking' | 'tool_running' | 'answering' | 'done' | 'error'

export type ReasoningStepKind = 'thought' | 'tool'

export type ReasoningStepStatus = 'pending' | 'running' | 'success' | 'error'

export interface ReasoningToolState {
  name: string
  displayName: string
  inputSummary?: string
  resultSummary?: string
}

export interface ReasoningStep {
  id: string
  kind: ReasoningStepKind
  title: string
  content: string
  status: ReasoningStepStatus
  startedAt: number
  endedAt?: number
  durationMs?: number
  tool?: ReasoningToolState
  isMarkdown?: boolean
  isDefaultExpand?: boolean
}

export interface ReasoningState {
  status: AgentMessageStatus
  title: string
  expanded: boolean
  startedAt: number
  endedAt?: number
  elapsedMs?: number
  steps: ReasoningStep[]
}

export interface AssistantAnswerState {
  status: 'idle' | 'answering' | 'done' | 'error'
  content: string
  startedAt?: number
  endedAt?: number
  error?: string
}

export interface AgentStreamBaseEvent {
  type: string
  messageId?: string
  sessionId?: string
  timestamp?: string
}

export interface MessageStartEvent extends AgentStreamBaseEvent {
  type: 'message_start'
  messageId: string
  sessionId?: string
}

export interface ThoughtStartEvent extends AgentStreamBaseEvent {
  type: 'thought_start'
  thoughtId?: string
  id?: string
  title?: string
  content?: string
}

export interface ThoughtDeltaEvent extends AgentStreamBaseEvent {
  type: 'thought_delta'
  thoughtId?: string
  id?: string
  delta: string
}

export interface ToolStartEvent extends AgentStreamBaseEvent {
  type: 'tool_start'
  toolCallId?: string
  id?: string
  toolName: string
  displayName?: string
  inputSummary?: string
  arguments?: Record<string, unknown>
}

export interface ToolDeltaEvent extends AgentStreamBaseEvent {
  type: 'tool_delta'
  toolCallId?: string
  id?: string
  delta: string
}

export interface ToolResultEvent extends AgentStreamBaseEvent {
  type: 'tool_result'
  toolCallId?: string
  id?: string
  summary?: string
  data?: unknown
  error?: string
}

export interface ToolEndEvent extends AgentStreamBaseEvent {
  type: 'tool_end'
  toolCallId?: string
  id?: string
  status?: 'success' | 'error'
  durationMs?: number
  error?: string
}

export interface ThoughtEndEvent extends AgentStreamBaseEvent {
  type: 'thought_end'
  thoughtId?: string
  id?: string
  durationMs?: number
}

export interface AnswerStartEvent extends AgentStreamBaseEvent {
  type: 'answer_start'
}

export interface AnswerDeltaEvent extends AgentStreamBaseEvent {
  type: 'answer_delta'
  delta: string
}

export interface AnswerEndEvent extends AgentStreamBaseEvent {
  type: 'answer_end'
  durationMs?: number
}

export interface StreamErrorEvent extends AgentStreamBaseEvent {
  type: 'error'
  message: string
  code?: string
  recoverable?: boolean
}

export type NewAgentStreamEvent =
  | MessageStartEvent
  | ThoughtStartEvent
  | ThoughtDeltaEvent
  | ToolStartEvent
  | ToolDeltaEvent
  | ToolResultEvent
  | ToolEndEvent
  | ThoughtEndEvent
  | AnswerStartEvent
  | AnswerDeltaEvent
  | AnswerEndEvent
  | StreamErrorEvent

export type LegacyAgentStreamEvent =
  | { type: 'agent_update'; agent: string; status: 'active' | 'done' | 'failed' }
  | { type: 'risk_update'; level: string; details?: string[] }
  | { type: 'plan_update'; name: string; status: string; total: number; completed: number; failed: number }
  | { type: 'session_init'; sessionId: string }
  | { type: 'agent_message'; agent: string; content: string }
  | {
      type: 'evidence_update'
      agent: string
      items: Array<{
        citation_id: string
        content: string
        document_title: string
        source_uri?: string
        heading_path?: string[]
        score?: number
      }>
    }
  | {
      type: 'trace_update'
      phase: string
      status: string
      title: string
      detail?: string
      tool_name?: string
      metadata?: Record<string, unknown>
    }

export type AgentStreamEvent = NewAgentStreamEvent | LegacyAgentStreamEvent

