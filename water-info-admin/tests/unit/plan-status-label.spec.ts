/**
 * Feature: plan-human-review, Property 1: 'draft' 是唯一映射到"草案"的状态标签
 *
 * Validates: Requirements 1.1, 1.2, 9.1
 *
 * For any string `s`, `statusLabel(s) === "草案"` if and only if `s === "draft"`.
 */
import { describe, expect } from 'vitest'
import { test, fc } from '@fast-check/vitest'
import { statusLabel } from '@/views/ai/plan/statusLabel'

describe('statusLabel — Property 1: labelOf(s) === "草案" ⇔ s === "draft"', () => {
    test.prop(
        [fc.string()],
        { numRuns: 20 },
    )('arbitrary string maps to "草案" iff it equals "draft"', (s) => {
        const result = statusLabel(s)
        if (s === 'draft') {
            expect(result).toBe('草案')
        } else {
            expect(result).not.toBe('草案')
        }
    })
})
