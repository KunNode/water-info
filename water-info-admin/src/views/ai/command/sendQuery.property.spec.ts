/**
 * Feature: ai-session-history-resume, Property 5: sendQuery carries session_id
 *
 * Validates: Requirements 3.1
 *
 * Invariant: for any non-empty `currentSessionId` established on the
 * `aiConversation` store and any non-empty `queryText` dispatched by the
 * user, the `sendQuery` path in `views/ai/command/index.vue` MUST call
 * `useAgentStream.start(url, payload)` with
 *
 *   payload.sessionId === store.currentSessionId
 *
 * i.e. strict equality to the store's current session id. The property
 * covers the "load-then-send" code path (Req 3.1): first `loadSession`
 * succeeds and hydrates `currentSessionId`, then `sendQuery(queryText)`
 * is invoked.
 *
 * Spec: `.kiro/specs/ai-session-history-resume/design.md` §9 / Property 5
 *       and `tasks.md` Task 9.2.
 */
import { describe, expect, vi, afterEach } from 'vitest'
import { test, fc } from '@fast-check/vitest'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import { createRouter, createMemoryHistory, type Router } from 'vue-router'
import type { ConversationDetail } from '@/types'

// ── Hoisted mocks ──────────────────────────────────────────────────────
//
// `vi.hoisted` ensures the spies exist before `vi.mock` factories run and
// before the view module imports the mocked modules. We need:
//
//   - `getConversationMessages` to resolve with a canned ConversationDetail
//     so `loadSession` succeeds and writes `currentSessionId`.
//   - `getStreamUrl` to return a stable URL so the first `start` arg is
//     deterministic (not strictly required for the property, but simplifies
//     assertions).
//   - `listConversations` to resolve with an empty list so `fetchSessions`
//     and the post-send `store.fetchSessions()` don't blow up.
//   - `useAgentStream.start` as a spy: we assert on its first-call
//     arguments to validate the property.
//   - Situation store methods that `onMounted` invokes (`connectAssessmentStream`,
//     `ensureFresh`) must be no-ops in jsdom to avoid EventSource/setInterval
//     leaks across 100 iterations.

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
    onEvent: vi.fn(),
    onText: vi.fn(),
}))

const situationMocks = vi.hoisted(() => ({
    connectAssessmentStream: vi.fn(),
    ensureFresh: vi.fn().mockResolvedValue(undefined),
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
            onEvent: streamMocks.onEvent,
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

// ElMessage is invoked on error paths only — stubbing keeps the console
// clean across iterations.
vi.mock('element-plus', async () => {
    const actual = await vi.importActual<Record<string, unknown>>('element-plus')
    return {
        ...actual,
        ElMessage: Object.assign(vi.fn(), {
            success: vi.fn(),
            warning: vi.fn(),
            error: vi.fn(),
            info: vi.fn(),
        }),
    }
})

// Import AFTER the mocks so the view binds to the mocked modules.
import CommandView from '@/views/ai/command/index.vue'
import { useAiConversationStore } from '@/stores/aiConversation'

// ── Tuning ─────────────────────────────────────────────────────────────

const PBT_RUNS = 100

// ── Arbitraries ────────────────────────────────────────────────────────

// Non-empty sessionId — any non-empty string is a valid backend id.
const sessionIdArb: fc.Arbitrary<string> = fc
    .string({ minLength: 1, maxLength: 40 })
    .filter((s) => s.length > 0)

// Non-empty queryText, constrained to visible characters so the store's
// `queryText.trim()` guard is satisfied and `sendQuery` doesn't short-circuit.
const queryTextArb: fc.Arbitrary<string> = fc
    .string({ minLength: 1, maxLength: 200 })
    .map((s) => (s.trim().length > 0 ? s : `query ${s}x`))

// ── Test helpers ───────────────────────────────────────────────────────

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

const emptyDetail = (): ConversationDetail => ({
    session_id: '',
    title: '',
    messages: [],
    snapshot: null,
    has_more: false,
    created_at: null as unknown as string,
})

// Stubs for all in-view sub-components. `ChatPanel` is a real "stub"
// component that re-emits `send` so we can drive `sendQuery` from the test
// without mounting the real component tree (which pulls in Element Plus,
// markdown rendering, etc.).
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

afterEach(() => {
    // Clear spies so call counts are per-iteration, not cumulative.
    streamMocks.start.mockReset()
    apiMocks.getConversationMessages.mockReset()
    apiMocks.listConversations.mockReset()
    situationMocks.connectAssessmentStream.mockReset()
    situationMocks.ensureFresh.mockReset().mockResolvedValue(undefined)
    localStorage.clear()
})

// ────────────────────────────────────────────────────────────────────────
// Property 5
// ────────────────────────────────────────────────────────────────────────

describe('Feature: ai-session-history-resume, Property 5: sendQuery carries session_id', () => {
    test.prop([sessionIdArb, queryTextArb], { numRuns: PBT_RUNS })(
        'payload.sessionId === store.currentSessionId after load-then-send',
        async (sessionId, queryText) => {
            // Fresh Pinia + mock state per iteration. `test.prop` runs the
            // predicate N times within a single Vitest test, so per-run
            // isolation lives here.
            setActivePinia(createPinia())
            streamMocks.start.mockReset()
            apiMocks.getConversationMessages.mockReset()
            apiMocks.listConversations.mockReset()

            apiMocks.listConversations.mockResolvedValue({ code: 200, message: 'ok', data: [] })
            apiMocks.getConversationMessages.mockResolvedValue({
                code: 200,
                message: 'ok',
                data: { ...emptyDetail(), session_id: sessionId },
            })
            // start() must return a resolved promise so the awaited `await start(...)`
            // inside sendQuery doesn't leave the component in a pending state.
            streamMocks.start.mockResolvedValue(undefined)

            const wrapper = await mountView()
            try {
                // Drive the "load then send" path exactly as the UI would:
                // 1. User clicks a session → handleSessionSelect → loadSession
                // 2. User types + presses send → ChatPanel emits 'send'
                const store = useAiConversationStore()
                await store.loadSession(sessionId)
                // Sanity check: loadSession populated currentSessionId.
                expect(store.currentSessionId).toBe(sessionId)

                const chatPanel = wrapper.findComponent({ name: 'ChatPanel' })
                expect(chatPanel.exists()).toBe(true)

                chatPanel.vm.$emit('send', queryText)
                await flushPromises()

                // Invariant: start() was called with payload whose sessionId
                // strictly equals store.currentSessionId.
                expect(streamMocks.start).toHaveBeenCalled()
                const [, payload] = streamMocks.start.mock.calls[0]
                expect(payload).toMatchObject({
                    message: queryText,
                    stream: true,
                    sessionId: store.currentSessionId,
                })
                expect((payload as { sessionId: string }).sessionId).toBe(sessionId)
            } finally {
                wrapper.unmount()
            }
        },
    )
})
