/**
 * Feature: ai-session-history-resume, Property 1: loadSession atomicity
 *
 * Validates: Requirements 1.1, 1.2, 1.3, 2.1
 *
 * For any non-empty `sessionId` (different from the current `currentSessionId`)
 * and any `ConversationDetail` returned by Messages_API, after
 * `store.loadSession(sessionId)` resolves successfully the following three
 * invariants must hold simultaneously:
 *
 *   1. `store.currentSessionId === sessionId`                    (Req 1.1)
 *   2. `getConversationMessages` is called exactly once with     (Req 1.2)
 *      `sessionId` as the first argument
 *   3. `store.messages.length === detail.messages.length`,       (Req 1.3, 2.1)
 *      corresponding `content` values are equal, and
 *      `store.messages[i].timestamp` is monotonically non-decreasing
 *
 * Spec: `.kiro/specs/ai-session-history-resume/design.md` §2 / Property 1
 *       and `tasks.md` Task 6.2.
 */
import { describe, expect, vi } from 'vitest'
import { test, fc } from '@fast-check/vitest'
import { createPinia, setActivePinia } from 'pinia'
import type { ConversationDetail, ConversationMessage } from '@/types'

// ── Hoisted mock for `@/api/flood` ─────────────────────────────────────
//
// `vi.hoisted` guarantees these `vi.fn()` references exist before the
// `vi.mock` factory (which is itself hoisted) runs, and before the store
// module imports them. Every function the store pulls from `@/api/flood`
// must be provided so module evaluation doesn't explode.

const mocks = vi.hoisted(() => ({
    getConversationMessages: vi.fn(),
    listConversations: vi.fn(),
    getConversation: vi.fn(),
    deleteConversation: vi.fn(),
    renameConversation: vi.fn(),
}))

vi.mock('@/api/flood', () => ({
    getConversationMessages: mocks.getConversationMessages,
    listConversations: mocks.listConversations,
    getConversation: mocks.getConversation,
    deleteConversation: mocks.deleteConversation,
    renameConversation: mocks.renameConversation,
}))

// Import after the mock so the store's module-level `import` wire is
// rerouted to the mock.
import { useAiConversationStore } from '@/stores/aiConversation'

// ── Tuning ─────────────────────────────────────────────────────────────

const PBT_RUNS = 100
const INITIAL_SESSION_ID = 'initial-session-id-fixture'

// ── Arbitraries ────────────────────────────────────────────────────────

// Non-empty sessionId, guaranteed different from INITIAL_SESSION_ID.
const sessionIdArb: fc.Arbitrary<string> = fc
    .string({ minLength: 1, maxLength: 40 })
    .filter((s) => s.length > 0 && s !== INITIAL_SESSION_ID)

// Monotonically non-decreasing timestamps via cumulative integer deltas so
// that `created_at`-ordered input round-trips through the store's explicit
// `messages.sort(...)` guard without permuting the logical order. This is
// the precondition for asserting `store.messages[i].content ===
// detail.messages[i].content` (Property 1 invariant 3).
const messagesArb: fc.Arbitrary<ConversationMessage[]> = fc
    .array(
        fc.record({
            role: fc.constantFrom<'user' | 'assistant'>('user', 'assistant'),
            content: fc.string(),
            deltaMs: fc.integer({ min: 0, max: 60_000 }),
        }),
        { maxLength: 12 },
    )
    .map((raws) => {
        const baseMs = 1_700_000_000_000 // 2023-11-14T..., safely < year 2100
        let cursor = baseMs
        return raws.map((raw, idx): ConversationMessage => {
            cursor += raw.deltaMs
            return {
                id: idx + 1,
                role: raw.role,
                content: raw.content,
                created_at: new Date(cursor).toISOString(),
            }
        })
    })

const detailArb: fc.Arbitrary<ConversationDetail> = fc
    .record({
        sessionId: sessionIdArb,
        messages: messagesArb,
        title: fc.string({ maxLength: 40 }),
    })
    .map(({ sessionId, messages, title }): ConversationDetail => ({
        session_id: sessionId,
        title,
        messages,
        snapshot: null,
        has_more: false,
        created_at: null,
    }))

// ────────────────────────────────────────────────────────────────────────
// Property 1
// ────────────────────────────────────────────────────────────────────────

describe('Feature: ai-session-history-resume, Property 1: loadSession atomicity', () => {
    test.prop([sessionIdArb, detailArb], { numRuns: PBT_RUNS })(
        'post-loadSession invariants hold for any valid sessionId and ConversationDetail',
        async (sessionId, detail) => {
            // Fresh pinia + mock state per iteration. `test.prop` runs the
            // predicate N times within one Vitest test, so `beforeEach` alone
            // wouldn't isolate iterations.
            setActivePinia(createPinia())
            mocks.getConversationMessages.mockReset()
            localStorage.clear()

            const store = useAiConversationStore()
            // Seed a different prior sessionId so the property precondition
            // (`sessionId !== currentSessionId`) is exercised.
            store.currentSessionId = INITIAL_SESSION_ID

            mocks.getConversationMessages.mockResolvedValue({
                code: 200,
                message: 'ok',
                data: detail,
            })

            await store.loadSession(sessionId)

            // Invariant 1 (Req 1.1): currentSessionId is updated.
            expect(store.currentSessionId).toBe(sessionId)

            // Invariant 2 (Req 1.2): exactly one call whose first arg is `sessionId`.
            expect(mocks.getConversationMessages).toHaveBeenCalledTimes(1)
            expect(mocks.getConversationMessages.mock.calls[0][0]).toBe(sessionId)

            // Invariant 3 (Req 1.3, 2.1): length, content, monotone timestamps.
            expect(store.messages.length).toBe(detail.messages.length)
            for (let i = 0; i < detail.messages.length; i += 1) {
                expect(store.messages[i].content).toBe(detail.messages[i].content)
            }
            for (let i = 1; i < store.messages.length; i += 1) {
                expect(store.messages[i].timestamp.getTime()).toBeGreaterThanOrEqual(
                    store.messages[i - 1].timestamp.getTime(),
                )
            }
        },
    )
})
