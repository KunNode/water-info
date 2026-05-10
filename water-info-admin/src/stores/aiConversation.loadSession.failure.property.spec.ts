/**
 * Feature: ai-session-history-resume, Property 6: loadSession failure preservation
 *
 * Validates: Requirements 4.2
 *
 * Failure-path invariant for `useAiConversationStore().loadSession`:
 *
 *   For any non-empty prior state S₀ = {
 *       currentSessionId,
 *       messages,
 *       snapshot,
 *       sessionTitle,
 *   },
 *   and any rejected `getConversationMessages` call (4xx / 5xx / NetworkError),
 *   after `loadSession(newSessionId)` returns (with a rethrown Error), the four
 *   reactive fields above MUST equal S₀ field-by-field.
 *
 * Spec: `.kiro/specs/ai-session-history-resume/design.md` §2 / §Error Handling
 *       and `tasks.md` Task 6.3.
 */
import { describe, expect, vi, beforeEach } from 'vitest'
import { test, fc } from '@fast-check/vitest'
import { createPinia, setActivePinia } from 'pinia'

// IMPORTANT: mock `@/api/flood` BEFORE importing the store module so that the
// store's top-level `import { getConversationMessages } from '@/api/flood'`
// binds to our mock.
vi.mock('@/api/flood', () => ({
    listConversations: vi.fn(),
    getConversation: vi.fn(),
    getConversationMessages: vi.fn(),
    deleteConversation: vi.fn(),
    renameConversation: vi.fn(),
}))

import { getConversationMessages } from '@/api/flood'
import { useAiConversationStore, type ChatMessageItem } from '@/stores/aiConversation'
import type { ConversationSnapshot } from '@/types'

const PBT_RUNS = 100

// ── Arbitraries ─────────────────────────────────────────────────────────
//
// Prior state S₀: must be "non-empty" per the property statement — so
// `currentSessionId` is a non-empty string, `messages` is a non-empty list
// of `ChatMessageItem`, and `sessionTitle` is non-empty. `snapshot` is
// optional (may be null) because the snapshot field is allowed to be null
// even when the session is fully loaded.

const chatMessageItemArb: fc.Arbitrary<ChatMessageItem> = fc.record(
    {
        id: fc.oneof(
            fc.integer({ min: 1, max: 1_000_000 }),
            fc.string({ minLength: 1, maxLength: 32 }),
        ),
        role: fc.constantFrom<'user' | 'assistant'>('user', 'assistant'),
        content: fc.string(),
        // Bounded to year 2100 to keep generators fast and timestamps comparable.
        timestamp: fc
            .integer({ min: 0, max: 4_102_444_800_000 })
            .map((ms) => new Date(ms)),
    },
    { requiredKeys: ['role', 'content', 'timestamp'] },
) as fc.Arbitrary<ChatMessageItem>

const snapshotArb: fc.Arbitrary<ConversationSnapshot | null> = fc.option(
    fc.record({
        risk_level: fc.constantFrom('none', 'low', 'moderate', 'high', 'critical'),
        plan_info: fc.constantFrom<Record<string, any> | null>(
            null,
            { plan_id: 'plan-1', plan_name: '防汛预案', status: 'executing', actions_count: 3 },
        ),
        agent_status_summary: fc.constantFrom<Record<string, any> | null>(
            null,
            { supervisor: 'done', risk_assessor: 'done' },
        ),
        query_count: fc.integer({ min: 0, max: 1000 }),
    }),
    { nil: null },
)

// Two distinct non-empty session IDs, so loadSession does NOT short-circuit
// via the `!sessionId` branch (which calls `clearCurrentSession`, a success
// path that this property is NOT testing).
const sessionIdPairArb = fc
    .tuple(
        fc.string({ minLength: 1, maxLength: 32 }),
        fc.string({ minLength: 1, maxLength: 32 }),
    )
    .filter(([prev, next]) => prev !== next && prev.length > 0 && next.length > 0)

// Failure shapes spanning 4xx / 5xx / network errors. The store's error
// handler only inspects `e.message`, so a plain `Error` is a faithful mock
// of anything Axios would surface in practice.
const rejectionArb: fc.Arbitrary<Error> = fc.oneof(
    fc
        .integer({ min: 400, max: 499 })
        .map((code) => new Error(`Request failed with status code ${code}`)),
    fc
        .integer({ min: 500, max: 599 })
        .map((code) => new Error(`Request failed with status code ${code}`)),
    fc.constantFrom(
        new Error('Network Error'),
        new Error('timeout of 0ms exceeded'),
        new Error('NetworkError: connection refused'),
    ),
)

// Prior state bundle.
const priorStateArb = fc.record({
    previousSessionId: fc.string({ minLength: 1, maxLength: 32 }),
    previousMessages: fc.array(chatMessageItemArb, { minLength: 1, maxLength: 6 }),
    previousSnapshot: snapshotArb,
    previousTitle: fc.string({ minLength: 1, maxLength: 40 }),
})

// ── Test setup ─────────────────────────────────────────────────────────

const getMessagesMock = vi.mocked(getConversationMessages)

beforeEach(() => {
    setActivePinia(createPinia())
    getMessagesMock.mockReset()
    // Silence the console.error emitted by the store's catch block so the
    // fast-check output stays readable across 100 iterations.
    vi.spyOn(console, 'error').mockImplementation(() => { })
    // Ensure localStorage starts clean each run (jsdom persists across tests).
    localStorage.clear()
})

// ────────────────────────────────────────────────────────────────────────
// Property 6
// ────────────────────────────────────────────────────────────────────────

describe('Feature: ai-session-history-resume, Property 6: loadSession failure preservation', () => {
    test.prop([priorStateArb, sessionIdPairArb, rejectionArb], { numRuns: PBT_RUNS })(
        'store.currentSessionId / messages / snapshot / sessionTitle equal S₀ after loadSession rejects',
        async (prior, [, newSessionId], err) => {
            const store = useAiConversationStore()

            // Install S₀ on the store. Direct assignment on a Pinia setup
            // store updates the underlying refs and is the idiomatic way to
            // seed state in tests without invoking (mocked) network flows.
            store.currentSessionId = prior.previousSessionId
            store.messages = prior.previousMessages
            store.snapshot = prior.previousSnapshot
            store.sessionTitle = prior.previousTitle

            // Deep-clone S₀ now so we can compare even if restoration used the
            // same object reference (the store's catch block happens to do so,
            // but this invariant is about value equality, not identity).
            const snapshotS0 = {
                currentSessionId: prior.previousSessionId,
                messages: prior.previousMessages.map((m) => ({
                    ...m,
                    timestamp: new Date(m.timestamp.getTime()),
                })),
                snapshot: prior.previousSnapshot
                    ? { ...prior.previousSnapshot }
                    : null,
                sessionTitle: prior.previousTitle,
            }

            // Arrange the failure: any call to getConversationMessages rejects
            // with the generated error (4xx / 5xx / network).
            getMessagesMock.mockRejectedValueOnce(err)

            // Act: loadSession must throw — the store rewraps the original
            // error as `Error('加载会话失败：<msg>')`.
            await expect(store.loadSession(newSessionId)).rejects.toThrow()

            // Assert: each tracked field is field-by-field equal to S₀.
            expect(store.currentSessionId).toBe(snapshotS0.currentSessionId)
            expect(store.sessionTitle).toBe(snapshotS0.sessionTitle)
            expect(store.snapshot).toEqual(snapshotS0.snapshot)

            expect(store.messages).toHaveLength(snapshotS0.messages.length)
            store.messages.forEach((m, idx) => {
                const original = snapshotS0.messages[idx]
                expect(m.role).toBe(original.role)
                expect(m.content).toBe(original.content)
                expect(m.id).toBe(original.id)
                expect(m.timestamp.getTime()).toBe(original.timestamp.getTime())
            })

            // The loading flag must be reset regardless of outcome.
            expect(store.isLoadingSession).toBe(false)
        },
    )
})
