/**
 * Unit tests for `case 'error'` inside `views/ai/command/index.vue`'s
 * `handleStreamEvent` (Task 9.1).
 *
 * Verifies the two-branch contract aligned with backend Task 3.3:
 *
 *   recoverable === false  → stop() + ElMessage.error(message) +
 *                            store.failAssistant(message, false)
 *   recoverable !== false  → soft-degrade (failAssistant(msg, true)),
 *                            stream NOT terminated, no top-level toast
 *
 * Covers: Requirements 4.4, 4.5
 *         design.md §5 (SSE error handling) and
 *         tasks.md Task 9.1.
 */
import { describe, expect, vi, beforeEach, afterEach, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import { createRouter, createMemoryHistory, type Router } from 'vue-router'
import type { AgentStreamEvent } from '@/types/agentStream'

// ── Hoisted mocks ──────────────────────────────────────────────────────

const apiMocks = vi.hoisted(() => ({
    getConversationMessages: vi.fn(),
    listConversations: vi.fn(),
    getConversation: vi.fn(),
    deleteConversation: vi.fn(),
    renameConversation: vi.fn(),
    getStreamUrl: vi.fn(() => '/api/v1/flood/query/stream'),
}))

const streamMocks = vi.hoisted(() => ({
    start: vi.fn<(url: string, payload: unknown) => Promise<void>>(),
    stop: vi.fn(),
    reset: vi.fn(),
    onEvent: vi.fn<(cb: (event: AgentStreamEvent) => void) => void>(),
    onText: vi.fn(),
    // Captured callback that `index.vue` passes to `onEvent(...)`.
    capturedHandler: null as ((event: AgentStreamEvent) => void) | null,
}))

const situationMocks = vi.hoisted(() => ({
    connectAssessmentStream: vi.fn(),
    ensureFresh: vi.fn().mockResolvedValue(undefined),
}))

const elMessageMocks = vi.hoisted(() => ({
    error: vi.fn(),
    success: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
}))

vi.mock('@/api/flood', () => ({
    getConversationMessages: apiMocks.getConversationMessages,
    listConversations: apiMocks.listConversations,
    getConversation: apiMocks.getConversation,
    deleteConversation: apiMocks.deleteConversation,
    renameConversation: apiMocks.renameConversation,
    getStreamUrl: apiMocks.getStreamUrl,
}))

vi.mock('@/composables/useAgentStream', async () => {
    const { ref } = await import('vue')
    return {
        useAgentStream: () => ({
            loading: ref(false),
            error: ref<string | null>(null),
            events: ref([]),
            plainText: ref(''),
            start: streamMocks.start,
            stop: streamMocks.stop,
            reset: streamMocks.reset,
            onEvent: (cb: (event: AgentStreamEvent) => void) => {
                streamMocks.capturedHandler = cb
                streamMocks.onEvent(cb)
            },
            onText: streamMocks.onText,
        }),
    }
})

vi.mock('@/stores/situation', async () => {
    const { defineStore } = await import('pinia')
    return {
        useSituationStore: defineStore('situation', () => ({
            latestAssessment: null,
            riskLevel: 'none',
            freshness: 'fresh',
            connection: 'idle',
            isLoading: false,
            refreshLatestAssessment: vi.fn(),
            ensureFresh: situationMocks.ensureFresh,
            connectAssessmentStream: situationMocks.connectAssessmentStream,
            resetForTest: vi.fn(),
        })),
    }
})

vi.mock('element-plus', async () => {
    const actual = await vi.importActual<Record<string, unknown>>('element-plus')
    return {
        ...actual,
        ElMessage: Object.assign(vi.fn(), elMessageMocks),
    }
})

// Import AFTER mocks.
import CommandView from '@/views/ai/command/index.vue'
import { useAiConversationStore } from '@/stores/aiConversation'

// ── Helpers ────────────────────────────────────────────────────────────

function makeRouter(): Router {
    return createRouter({
        history: createMemoryHistory(),
        routes: [
            { path: '/', name: 'Home', component: { template: '<div />' } },
            { path: '/ai/command', name: 'AICommand', component: { template: '<div />' } },
            { path: '/dashboard', name: 'Dashboard', component: { template: '<div />' } },
        ],
    })
}

const ChatPanelStub = {
    name: 'ChatPanel',
    emits: ['send'],
    template: '<div class="chat-panel-stub" />',
}

const globalStubs = {
    ChatPanel: ChatPanelStub,
    RiskPanel: true,
    PlanStatus: true,
    ActiveAlerts: true,
    SessionInfo: true,
    SessionDrawer: {
        name: 'SessionDrawer',
        template: '<div />',
        methods: { refresh() { /* no-op */ } },
    },
    'el-button': true,
    'el-icon': true,
    'el-input': true,
    'el-tag': true,
    'el-drawer': true,
}

async function mountView(): Promise<VueWrapper> {
    const router = makeRouter()
    await router.push('/ai/command')
    await router.isReady()

    const wrapper = mount(CommandView, {
        global: {
            plugins: [router],
            stubs: globalStubs,
        },
    })
    await flushPromises()
    await nextTick()
    return wrapper
}

beforeEach(() => {
    setActivePinia(createPinia())
    streamMocks.start.mockReset().mockResolvedValue(undefined)
    streamMocks.stop.mockReset()
    streamMocks.reset.mockReset()
    streamMocks.onEvent.mockReset()
    streamMocks.onText.mockReset()
    streamMocks.capturedHandler = null
    apiMocks.listConversations.mockReset().mockResolvedValue({ code: 200, message: 'ok', data: [] })
    apiMocks.getConversationMessages.mockReset()
    situationMocks.connectAssessmentStream.mockReset()
    situationMocks.ensureFresh.mockReset().mockResolvedValue(undefined)
    elMessageMocks.error.mockReset()
    elMessageMocks.success.mockReset()
    elMessageMocks.warning.mockReset()
    elMessageMocks.info.mockReset()
    localStorage.clear()
})

afterEach(() => {
    streamMocks.capturedHandler = null
})

// ────────────────────────────────────────────────────────────────────────

describe("handleStreamEvent → case 'error' (Task 9.1, Req 4.4/4.5)", () => {
    it('terminates the stream and surfaces a toast when recoverable === false', async () => {
        const wrapper = await mountView()
        try {
            const store = useAiConversationStore()
            // Seed an assistant message so failAssistant has a target.
            store.createAssistantMessage()

            expect(streamMocks.capturedHandler).toBeTypeOf('function')
            const handler = streamMocks.capturedHandler!

            handler({
                type: 'error',
                message: '会话历史加载失败，请稍后重试',
                code: 'memory_load_failed',
                recoverable: false,
            })
            await nextTick()

            // (1) stream terminated
            expect(streamMocks.stop).toHaveBeenCalledTimes(1)
            // (2) top-level toast raised with server-provided message
            expect(elMessageMocks.error).toHaveBeenCalledTimes(1)
            expect(elMessageMocks.error).toHaveBeenCalledWith('会话历史加载失败，请稍后重试')
            // (3) store marked assistant as hard-failed (recoverable=false)
            const assistant = store.messages[store.messages.length - 1]
            expect(assistant.role).toBe('assistant')
            expect(assistant.status).toBe('error')
            expect(assistant.error).toBe('会话历史加载失败，请稍后重试')
            expect(assistant.answer?.status).toBe('error')
        } finally {
            wrapper.unmount()
        }
    })

    it('keeps the stream alive and suppresses the toast when recoverable !== false', async () => {
        const wrapper = await mountView()
        try {
            const store = useAiConversationStore()
            store.createAssistantMessage()

            expect(streamMocks.capturedHandler).toBeTypeOf('function')
            const handler = streamMocks.capturedHandler!

            handler({
                type: 'error',
                message: '临时网络抖动',
                code: 'transient',
                recoverable: true,
            })
            await nextTick()

            expect(streamMocks.stop).not.toHaveBeenCalled()
            expect(elMessageMocks.error).not.toHaveBeenCalled()

            const assistant = store.messages[store.messages.length - 1]
            // Recoverable: error is recorded but message status is not
            // force-flipped to 'error'.
            expect(assistant.error).toBe('临时网络抖动')
            expect(assistant.status).not.toBe('error')
        } finally {
            wrapper.unmount()
        }
    })

    it('treats a missing `recoverable` field as recoverable (no stop, no toast)', async () => {
        const wrapper = await mountView()
        try {
            const store = useAiConversationStore()
            store.createAssistantMessage()

            const handler = streamMocks.capturedHandler!
            handler({
                type: 'error',
                message: '未知错误',
            } as AgentStreamEvent)
            await nextTick()

            expect(streamMocks.stop).not.toHaveBeenCalled()
            expect(elMessageMocks.error).not.toHaveBeenCalled()
        } finally {
            wrapper.unmount()
        }
    })
})
