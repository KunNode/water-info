<template>
  <aside class="fm-side" :class="{ collapsed }">
    <nav class="fm-side__nav">
      <div v-for="group in visibleGroups" :key="group.group" class="fm-side__group">
        <div v-show="!collapsed" class="fm-side__group-label">{{ group.group }}</div>
        <router-link
          v-for="item in group.items"
          :key="item.path"
          :to="item.path"
          class="fm-side__item"
          :class="{ active: isActive(item.path) }"
          :title="collapsed ? item.label : undefined"
        >
          <span class="icn">
            <el-icon><component :is="iconMap[item.icon]" /></el-icon>
          </span>
          <span v-show="!collapsed" class="label">{{ item.label }}</span>
          <span
            v-if="item.badge && !collapsed"
            class="fm-side__badge"
            :class="{ danger: item.badgeDanger }"
          >{{ item.badge }}</span>
        </router-link>
      </div>
    </nav>
    <div v-show="!collapsed" class="fm-side__footer">
      <span class="fm-dot ok" />
      <span>all systems nominal</span>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { computed, markRaw } from 'vue'
import { useRoute } from 'vue-router'
import { useAppStore } from '@/stores/app'
import { useUserStore } from '@/stores/user'
import { canAccess } from '@/utils/permission'
import {
  Odometer,
  Monitor,
  MapLocation,
  Cpu,
  DataAnalysis,
  Bell,
  Setting,
  MagicStick,
  Document,
  Reading,
  Place,
  User,
  Key,
  OfficeBuilding,
  Notebook,
} from '@element-plus/icons-vue'

// Map icon name → component. markRaw avoids Vue trying to make the icon reactive.
const iconMap: Record<string, unknown> = {
  Odometer: markRaw(Odometer),
  Monitor: markRaw(Monitor),
  MapLocation: markRaw(MapLocation),
  Cpu: markRaw(Cpu),
  DataAnalysis: markRaw(DataAnalysis),
  Bell: markRaw(Bell),
  Setting: markRaw(Setting),
  MagicStick: markRaw(MagicStick),
  Document: markRaw(Document),
  Reading: markRaw(Reading),
  Place: markRaw(Place),
  User: markRaw(User),
  Key: markRaw(Key),
  OfficeBuilding: markRaw(OfficeBuilding),
  Notebook: markRaw(Notebook),
}

interface NavItem {
  path: string
  label: string
  icon: string
  roles?: string[]
  badge?: string
  badgeDanger?: boolean
}
interface NavGroup {
  group: string
  items: NavItem[]
}

// Hand-authored nav: faster to iterate than deriving from router, and matches
// the FloodMind prototype grouping. Paths must exist in router/index.ts.
const NAV_GROUPS: NavGroup[] = [
  {
    group: '概览',
    items: [
      { path: '/dashboard', label: '指挥仪表盘', icon: 'Odometer' },
      { path: '/bigscreen', label: '大屏', icon: 'Monitor' },
    ],
  },
  {
    group: '监测 Monitor',
    items: [
      { path: '/monitor/station', label: '站点管理', icon: 'MapLocation', roles: ['ADMIN', 'OPERATOR'] },
      { path: '/monitor/sensor', label: '传感器', icon: 'Cpu', roles: ['ADMIN', 'OPERATOR'] },
    ],
  },
  {
    group: '数据 · 告警',
    items: [
      { path: '/data/observation', label: '观测数据', icon: 'DataAnalysis' },
      { path: '/warning/alarm', label: '告警管理', icon: 'Bell' },
      { path: '/warning/threshold', label: '阈值规则', icon: 'Setting', roles: ['ADMIN', 'OPERATOR'] },
    ],
  },
  {
    group: 'AI 中心',
    items: [
      { path: '/ai/command', label: 'AI 命令中心', icon: 'MagicStick' },
      { path: '/ai/plan', label: '应急预案', icon: 'Document' },
      { path: '/ai/knowledge', label: '知识库', icon: 'Reading', roles: ['ADMIN', 'OPERATOR'] },
    ],
  },
  {
    group: '系统',
    items: [
      { path: '/map', label: '流域地图', icon: 'Place' },
      { path: '/system/user', label: '用户', icon: 'User', roles: ['ADMIN'] },
      { path: '/system/role', label: '角色 & 权限', icon: 'Key', roles: ['ADMIN'] },
      { path: '/system/org', label: '组织部门', icon: 'OfficeBuilding', roles: ['ADMIN'] },
      { path: '/system/log', label: '操作日志', icon: 'Notebook', roles: ['ADMIN'] },
    ],
  },
]

const route = useRoute()
const appStore = useAppStore()
const userStore = useUserStore()

const collapsed = computed(() => appStore.sidebarCollapsed)

const visibleGroups = computed<NavGroup[]>(() => {
  return NAV_GROUPS
    .map((g) => ({
      group: g.group,
      items: g.items.filter((it) => !it.roles || canAccess(userStore.roles, it.roles)),
    }))
    .filter((g) => g.items.length > 0)
})

function isActive(path: string): boolean {
  return route.path === path || route.path.startsWith(path + '/')
}
</script>

<style scoped lang="scss">
.fm-side {
  grid-row: 2;
  grid-column: 1;
  background: linear-gradient(180deg, rgba(17, 26, 44, 0.6), rgba(11, 18, 32, 0.2));
  border-right: 1px solid var(--fm-line);
  padding: 10px 10px 14px;
  overflow-y: auto;
  backdrop-filter: blur(8px);
  display: flex;
  flex-direction: column;
  min-height: 0;

  &.collapsed {
    padding: 10px 6px 14px;
  }
}

html:not(.dark) .fm-side {
  background: linear-gradient(180deg, #ffffff 0%, #f7f8fb 100%);
}

.fm-side__nav {
  flex: 1;
  min-height: 0;
}

.fm-side__group-label {
  padding: 14px 10px 6px;
  font-family: var(--fm-font-mono);
  font-size: 10px;
  letter-spacing: 0.18em;
  color: var(--fm-fg-dim);
  text-transform: uppercase;
}

.fm-side__item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 10px;
  border-radius: var(--fm-radius-sm);
  font-size: 13px;
  color: var(--fm-fg-soft);
  cursor: pointer;
  position: relative;
  user-select: none;
  text-decoration: none;

  .fm-side.collapsed & {
    justify-content: center;
    padding: 8px 0;
  }

  &:hover {
    background: var(--fm-bg-2);
    color: var(--fm-fg);
  }

  &.active {
    background: linear-gradient(90deg, rgba(47, 123, 255, 0.18), rgba(73, 225, 255, 0.05) 60%, transparent);
    color: var(--fm-fg);
    font-weight: 500;
  }
  &.active::before {
    content: "";
    position: absolute;
    left: 0;
    top: 6px;
    bottom: 6px;
    width: 3px;
    border-radius: 2px;
    background: var(--fm-grad-brand);
    box-shadow: 0 0 8px var(--fm-brand-2);
  }

  .icn {
    width: 16px;
    height: 16px;
    display: grid;
    place-items: center;
    color: var(--fm-fg-mute);
    font-size: 16px;
    flex-shrink: 0;
  }
  &.active .icn {
    color: var(--fm-brand-2);
  }

  .label {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.fm-side__badge {
  margin-left: auto;
  font-family: var(--fm-font-mono);
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 8px;
  background: var(--fm-bg-3);
  color: var(--fm-fg-mute);

  &.danger {
    background: rgba(255, 90, 106, 0.15);
    color: #ff8a96;
    box-shadow: 0 0 0 1px rgba(255, 90, 106, 0.3);
  }
}

.fm-side__footer {
  padding: 18px 10px 0;
  margin-top: 20px;
  border-top: 1px solid var(--fm-line);
  display: flex;
  gap: 10px;
  align-items: center;
  font-size: 11px;
  color: var(--fm-fg-mute);
  font-family: var(--fm-font-mono);
}

@media (max-width: 760px) {
  .fm-side {
    padding: 10px 6px 14px;
  }

  .fm-side__group-label,
  .fm-side__footer,
  .fm-side__item .label,
  .fm-side__badge {
    display: none !important;
  }

  .fm-side__item {
    justify-content: center;
    padding: 8px 0;
  }
}
</style>
