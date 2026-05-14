/**
 * Component tests for save / approve UX timing
 *
 * Validates: Requirements 3.5, 9.7, 9.8, 9.9
 *
 * Tests:
 * 1. Success toast displays for ≥ 2 seconds after save (Req 3.5)
 * 2. Submit button is disabled during loading state (Req 9.7)
 * 3. On failure, the opinion field retains its original value (Req 9.9)
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'
import ElementPlus, { ElMessage } from 'element-plus'

// Mock the API module
vi.mock('@/api/flood', () => ({
    getPlans: vi.fn().mockResolvedValue({ data: { records: [], total: 0 } }),
    getPlan: vi.fn(),
    executePlan: vi.fn(),
    updatePlan: vi.fn(),
    approvePlan: vi.fn(),
    getPlanAudits: vi.fn(),
}))

// Mock vue-router
vi.mock('vue-router', () => ({
    onBeforeRouteLeave: vi.fn(),
    useRouter: () => ({ push: vi.fn() }),
    useRoute: () => ({ params: {} }),
    createRouter: () => ({
        push: vi.fn(),
        replace: vi.fn(),
        beforeEach: vi.fn(),
        afterEach: vi.fn(),
        install: vi.fn(),
        currentRoute: { value: { path: '/' } },
    }),
    createWebHistory: () => ({}),
}))

// Mock marked
vi.mock('marked', () => ({
    marked: { parse: (s: string) => `<p>${s}</p>` },
}))

// Mock dompurify
vi.mock('dompurify', () => ({
    default: { sanitize: (s: string) => s },
}))

// Mock ElMessage
vi.mock('element-plus', async (importOriginal) => {
    const actual = await importOriginal<typeof import('element-plus')>()
    return {
        ...actual,
        ElMessage: {
            success: vi.fn(),
            error: vi.fn(),
            warning: vi.fn(),
            info: vi.fn(),
        },
        ElMessageBox: {
            confirm: vi.fn().mockResolvedValue('confirm'),
        },
    }
})

import { updatePlan, approvePlan, getPlan } from '@/api/flood'
import { useUserStore } from '@/stores/user'
import PlanIndex from '@/views/ai/plan/index.vue'

const mockPlan = {
    id: 'plan-001',
    sessionId: 'session-001',
    riskLevel: 'high' as const,
    summary: '# Test Plan',
    actions: [{ id: 'a-1', description: 'Action 1', priority: '1', assignee: 'User', status: 'pending' }],
    resources: [{ id: 1, type: 'sandbag', name: '沙袋', quantity: 100, location: '仓库' }],
    notifications: [{ id: 1, channel: 'sms', target: '13800000000', message: 'test', status: 'pending' }],
    status: 'draft' as const,
    version: 3,
    createdAt: '2026-01-01T00:00:00Z',
    updatedAt: '2026-01-01T00:00:00Z',
}

function createWrapper() {
    const pinia = createPinia()
    setActivePinia(pinia)

    // Set up user store with ADMIN role
    const store = useUserStore()
    store.$patch({
        userInfo: { id: 'u-1', username: 'admin', realName: 'Admin', roles: ['ADMIN'] },
        token: 'fake-token',
    })

    return mount(PlanIndex, {
        global: {
            plugins: [pinia, ElementPlus],
            stubs: {
                teleport: true,
            },
        },
    })
}

describe('Plan save/approve UX timing', () => {
    beforeEach(() => {
        vi.useFakeTimers()
        vi.clearAllMocks()
    })

    afterEach(() => {
        vi.useRealTimers()
    })

    describe('Req 3.5: Success toast displays for ≥ 2 seconds after save', () => {
        it('calls ElMessage.success with duration >= 2000ms on successful save', async () => {
            const updatedPlan = { ...mockPlan, version: 4 }
            vi.mocked(updatePlan).mockResolvedValue({ data: updatedPlan } as any)
            vi.mocked(getPlan).mockResolvedValue({ data: updatedPlan } as any)

            const wrapper = createWrapper()
            await flushPromises()

            // Simulate opening detail and entering edit mode
            const vm = wrapper.vm as any
            vm.currentPlan = { ...mockPlan }
            vm.drawerVisible = true
            vm.editMode = true
            vm.draftPlan = { ...mockPlan, summary: '# Modified Plan' }
            await nextTick()

            // Trigger save
            await vm.handleSave()
            await flushPromises()

            expect(ElMessage.success).toHaveBeenCalledWith(
                expect.objectContaining({
                    message: '保存成功',
                    duration: expect.any(Number),
                }),
            )

            // Verify duration is >= 2000
            const call = vi.mocked(ElMessage.success).mock.calls[0][0] as any
            expect(call.duration).toBeGreaterThanOrEqual(2000)

            wrapper.unmount()
        })
    })

    describe('Req 9.7: Submit button disabled during loading', () => {
        it('approve submit button is disabled while approvalLoading is true', async () => {
            // Make approvePlan hang (never resolve) to keep loading state
            let resolveApprove!: (v: any) => void
            vi.mocked(approvePlan).mockImplementation(
                () => new Promise((resolve) => { resolveApprove = resolve }),
            )

            const wrapper = createWrapper()
            await flushPromises()

            const vm = wrapper.vm as any
            vm.currentPlan = { ...mockPlan }
            vm.drawerVisible = true
            vm.approvalDialogVisible = true
            vm.approvalOpinion = '同意执行'
            await nextTick()

            // Verify button is enabled before submit
            expect(vm.approvalLoading).toBe(false)
            expect(vm.opinionValid).toBe(true)

            // Trigger approve (will hang)
            const approvePromise = vm.handleApprove()
            await nextTick()

            // Now loading should be true, button should be disabled
            expect(vm.approvalLoading).toBe(true)

            // Resolve to clean up
            resolveApprove({ data: { planId: 'plan-001', status: 'approved', version: 4, auditRecordId: 1 } })
            vi.mocked(getPlan).mockResolvedValue({ data: { ...mockPlan, status: 'approved', version: 4 } } as any)
            await approvePromise
            await flushPromises()

            wrapper.unmount()
        })

        it('save button is disabled while saving is true', async () => {
            let resolveSave!: (v: any) => void
            vi.mocked(updatePlan).mockImplementation(
                () => new Promise((resolve) => { resolveSave = resolve }),
            )

            const wrapper = createWrapper()
            await flushPromises()

            const vm = wrapper.vm as any
            vm.currentPlan = { ...mockPlan }
            vm.drawerVisible = true
            vm.editMode = true
            vm.draftPlan = { ...mockPlan, summary: '# Changed' }
            await nextTick()

            // Verify saving is false before
            expect(vm.saving).toBe(false)

            // Trigger save (will hang)
            const savePromise = vm.handleSave()
            await nextTick()

            // Now saving should be true
            expect(vm.saving).toBe(true)

            // Resolve to clean up
            resolveSave({ data: { ...mockPlan, version: 4 } })
            await savePromise
            await flushPromises()

            wrapper.unmount()
        })
    })

    describe('Req 9.9: On failure, opinion field retains its original value', () => {
        it('preserves approvalOpinion when approve request fails', async () => {
            vi.mocked(approvePlan).mockRejectedValue(new Error('版本冲突'))

            const wrapper = createWrapper()
            await flushPromises()

            const vm = wrapper.vm as any
            vm.currentPlan = { ...mockPlan }
            vm.drawerVisible = true
            vm.approvalDialogVisible = true
            vm.approvalOpinion = '同意执行，已补充了北闸站的撤离路径。'
            await nextTick()

            const originalOpinion = vm.approvalOpinion

            // Trigger approve which will fail
            await vm.handleApprove()
            await flushPromises()

            // Opinion should be preserved
            expect(vm.approvalOpinion).toBe(originalOpinion)
            // Dialog should remain open
            expect(vm.approvalDialogVisible).toBe(true)
            // Error message should be shown
            expect(ElMessage.error).toHaveBeenCalled()

            wrapper.unmount()
        })

        it('preserves draftPlan content when save request fails', async () => {
            vi.mocked(updatePlan).mockRejectedValue(new Error('保存失败'))

            const wrapper = createWrapper()
            await flushPromises()

            const vm = wrapper.vm as any
            vm.currentPlan = { ...mockPlan }
            vm.drawerVisible = true
            vm.editMode = true
            const modifiedSummary = '# Modified content that should be preserved'
            vm.draftPlan = { ...mockPlan, summary: modifiedSummary }
            await nextTick()

            // Trigger save which will fail
            await vm.handleSave()
            await flushPromises()

            // Draft content should be preserved (not rolled back)
            expect(vm.draftPlan.summary).toBe(modifiedSummary)
            // Edit mode should remain active
            expect(vm.editMode).toBe(true)
            // Error message should be shown
            expect(ElMessage.error).toHaveBeenCalled()

            wrapper.unmount()
        })
    })

    describe('Req 9.8: Success toast for approve displays for ≥ 2 seconds', () => {
        it('calls ElMessage.success with duration >= 2000ms on successful approve', async () => {
            vi.mocked(approvePlan).mockResolvedValue({
                data: { planId: 'plan-001', status: 'approved', version: 4, auditRecordId: 1 },
            } as any)
            vi.mocked(getPlan).mockResolvedValue({
                data: { ...mockPlan, status: 'approved', version: 4 },
            } as any)

            const wrapper = createWrapper()
            await flushPromises()

            const vm = wrapper.vm as any
            vm.currentPlan = { ...mockPlan }
            vm.drawerVisible = true
            vm.approvalDialogVisible = true
            vm.approvalOpinion = '同意执行'
            await nextTick()

            await vm.handleApprove()
            await flushPromises()

            expect(ElMessage.success).toHaveBeenCalledWith(
                expect.objectContaining({
                    message: '批准成功',
                    duration: expect.any(Number),
                }),
            )

            const call = vi.mocked(ElMessage.success).mock.calls[0][0] as any
            expect(call.duration).toBeGreaterThanOrEqual(2000)

            wrapper.unmount()
        })
    })
})
