/**
 * Feature: ai-session-history-resume, Property 2: metadata round-trip
 *
 * Validates: Requirements 2.2, 2.3, 2.4, 2.5, 3.6
 *
 * Round-trip invariant for `mapServerMessageToChatItem`: given an arbitrary
 * `conversation_messages` row (including empty arrays, missing fields, mixed
 * `kind=thought|tool`, and fully-absent `reasoning_steps` / `execution_traces`),
 * the mapped `ChatMessageItem` must satisfy:
 *
 *   - `metadata.reasoning_steps` non-empty on an assistant row
 *        ⇒ `output.reasoning.steps.length === input.reasoning_steps.length`
 *          and for every step `title / content / kind / status / tool.name`
 *          are equivalent (per the documented coercion rules).
 *   - `metadata.execution_traces` non-empty
 *        ⇒ `output.traces.length === input.execution_traces.length`
 *          and `phase / status / title / tool_name` are equivalent.
 *   - Both missing or empty
 *        ⇒ `output.reasoning === undefined` AND `output.traces === undefined`.
 *   - `role === 'user'`
 *        ⇒ `output.reasoning === undefined` (irrespective of metadata).
 *
 * Spec: `.kiro/specs/ai-session-history-resume/design.md` §1 / §2
 *       and `tasks.md` Task 5.2.
 */
import { describe, expect } from 'vitest'
import { test, fc } from '@fast-check/vitest'
import {
    mapServerMessageToChatItem,
    type RawExecutionTrace,
    type RawReasoningStep,
} from '@/stores/aiConversation'
import type { ConversationMessage } from '@/types'

// ── Arbitraries ─────────────────────────────────────────────────────────
//
// The generators constrain `title`/`content`/`phase`/`tool_name` to actual
// strings so the round-trip assertions compare verbatim. Variation comes
// from (a) the `kind` / `status` normalisation rules, (b) optional fields,
// (c) mixed presence of the `tool` sub-record, and (d) the top-level metadata
// keys being absent, `undefined`, or the empty array.

const PBT_RUNS = 100

const reasoningStepArb: fc.Arbitrary<RawReasoningStep> = fc.record(
    {
        id: fc.option(fc.oneof(fc.string(), fc.integer()), { nil: undefined }),
        // Include arbitrary non-`'tool'` strings so the default-to-`thought` branch runs.
        kind: fc.option(
            fc.oneof(fc.constantFrom<string>('thought', 'tool'), fc.string()),
            { nil: undefined },
        ),
        title: fc.option(fc.string(), { nil: undefined }),
        content: fc.option(fc.string(), { nil: undefined }),
        // Include arbitrary non-`'error'` strings so the default-to-`success` branch runs.
        status: fc.option(
            fc.oneof(
                fc.constantFrom<string>('pending', 'running', 'success', 'error'),
                fc.string(),
            ),
            { nil: undefined },
        ),
        started_at: fc.option(fc.integer({ min: 0, max: 2 ** 40 }), { nil: undefined }),
        ended_at: fc.option(fc.integer({ min: 0, max: 2 ** 40 }), { nil: undefined }),
        duration_ms: fc.option(fc.integer({ min: 0, max: 1_000_000 }), { nil: undefined }),
        tool: fc.option(
            fc.record(
                {
                    name: fc.string(),
                    display_name: fc.option(fc.string(), { nil: undefined }),
                    input_summary: fc.option(fc.string(), { nil: undefined }),
                    result_summary: fc.option(fc.string(), { nil: undefined }),
                },
                { requiredKeys: ['name'] },
            ),
            { nil: undefined },
        ),
    },
    { requiredKeys: [] },
) as fc.Arbitrary<RawReasoningStep>

const executionTraceArb: fc.Arbitrary<RawExecutionTrace> = fc.record(
    {
        phase: fc.string(),
        status: fc.string(),
        title: fc.string(),
        detail: fc.option(fc.string(), { nil: undefined }),
        tool_name: fc.option(fc.string(), { nil: undefined }),
        metadata: fc.option(fc.object({ maxDepth: 1, maxKeys: 4 }), { nil: undefined }),
    },
    { requiredKeys: ['phase', 'status', 'title'] },
) as fc.Arbitrary<RawExecutionTrace>

// Top-level metadata: every field is optional so the generator naturally
// produces `{}`, `{ reasoning_steps: [] }`, mixed, fully-populated, etc.
const metadataArb = fc.record(
    {
        reasoning_steps: fc.option(fc.array(reasoningStepArb, { maxLength: 6 }), { nil: undefined }),
        execution_traces: fc.option(fc.array(executionTraceArb, { maxLength: 6 }), { nil: undefined }),
    },
    { requiredKeys: [] },
)

const roleArb: fc.Arbitrary<'user' | 'assistant'> = fc.constantFrom('user', 'assistant')

const conversationMessageArb: fc.Arbitrary<ConversationMessage> = fc.record(
    {
        id: fc.option(fc.integer({ min: 1, max: 10_000_000 }), { nil: undefined }),
        role: roleArb,
        content: fc.string(),
        metadata: metadataArb,
        created_at: fc.option(
            fc
                .integer({ min: 0, max: 4_102_444_800_000 }) // up to year 2100
                .map((ms) => new Date(ms).toISOString()),
            { nil: null },
        ),
    },
    { requiredKeys: ['role', 'content'] },
) as fc.Arbitrary<ConversationMessage>

// ── Helpers: expected coercion matching `deserializeReasoningState` ────

function expectedKind(raw: unknown): 'thought' | 'tool' {
    return raw === 'tool' ? 'tool' : 'thought'
}

function expectedStatus(raw: unknown): 'success' | 'error' {
    return raw === 'error' ? 'error' : 'success'
}

function coerceString(raw: unknown): string {
    return typeof raw === 'string' ? raw : String(raw ?? '')
}

function isNonEmptyArray<T>(raw: unknown): raw is T[] {
    return Array.isArray(raw) && raw.length > 0
}

// ────────────────────────────────────────────────────────────────────────
// Property 2
// ────────────────────────────────────────────────────────────────────────

describe('Feature: ai-session-history-resume, Property 2: metadata round-trip', () => {
    test.prop([conversationMessageArb], { numRuns: PBT_RUNS })(
        'reasoning_steps round-trip matches length and per-step field equivalence',
        (msg) => {
            const item = mapServerMessageToChatItem(msg)
            const rawSteps = (msg.metadata ?? {}).reasoning_steps

            if (msg.role === 'assistant' && isNonEmptyArray<RawReasoningStep>(rawSteps)) {
                expect(item.reasoning).toBeDefined()
                expect(item.reasoning!.steps.length).toBe(rawSteps.length)

                rawSteps.forEach((raw, idx) => {
                    const step = item.reasoning!.steps[idx]
                    expect(step.kind).toBe(expectedKind(raw.kind))
                    expect(step.status).toBe(expectedStatus(raw.status))
                    expect(step.title).toBe(coerceString(raw.title))
                    expect(step.content).toBe(coerceString(raw.content))

                    if (raw.tool && typeof raw.tool === 'object') {
                        expect(step.tool).toBeDefined()
                        expect(step.tool!.name).toBe(coerceString(raw.tool.name))
                    } else {
                        expect(step.tool).toBeUndefined()
                    }
                })
            }
        },
    )

    test.prop([conversationMessageArb], { numRuns: PBT_RUNS })(
        'execution_traces round-trip matches length and per-trace field equivalence',
        (msg) => {
            const item = mapServerMessageToChatItem(msg)
            const rawTraces = (msg.metadata ?? {}).execution_traces

            if (isNonEmptyArray<RawExecutionTrace>(rawTraces)) {
                expect(item.traces).toBeDefined()
                expect(item.traces!.length).toBe(rawTraces.length)

                rawTraces.forEach((raw, idx) => {
                    const trace = item.traces![idx]
                    expect(trace.phase).toBe(coerceString(raw.phase))
                    expect(trace.status).toBe(coerceString(raw.status))
                    expect(trace.title).toBe(coerceString(raw.title))

                    if (raw.tool_name !== undefined && raw.tool_name !== null) {
                        expect(trace.tool_name).toBe(coerceString(raw.tool_name))
                    } else {
                        expect(trace.tool_name).toBeUndefined()
                    }
                })
            }
        },
    )

    test.prop([conversationMessageArb], { numRuns: PBT_RUNS })(
        'missing or empty reasoning_steps / execution_traces yield undefined fields',
        (msg) => {
            const item = mapServerMessageToChatItem(msg)
            const meta = msg.metadata ?? {}
            const hasReasoning =
                msg.role === 'assistant' && isNonEmptyArray<RawReasoningStep>(meta.reasoning_steps)
            const hasTraces = isNonEmptyArray<RawExecutionTrace>(meta.execution_traces)

            if (!hasReasoning) {
                expect(item.reasoning).toBeUndefined()
            }
            if (!hasTraces) {
                expect(item.traces).toBeUndefined()
            }
        },
    )

    test.prop([conversationMessageArb], { numRuns: PBT_RUNS })(
        'user role messages always have reasoning === undefined',
        (msg) => {
            const userMsg: ConversationMessage = { ...msg, role: 'user' }
            const item = mapServerMessageToChatItem(userMsg)
            expect(item.reasoning).toBeUndefined()
        },
    )
})
