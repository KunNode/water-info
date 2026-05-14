/**
 * Maps plan status values to their Chinese display labels.
 */
export const statusLabel = (status: string): string => {
    const map: Record<string, string> = {
        draft: '草案',
        approved: '已批准',
        executing: '执行中',
        completed: '已完成',
        failed: '执行失败',
        cancelled: '已取消'
    }
    return map[status] || status || '未知'
}
