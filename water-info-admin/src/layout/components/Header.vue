<template>
  <header class="fm-topbar">
    <div class="fm-topbar__collapse" @click="appStore.toggleSidebar">
      <el-icon>
        <Expand v-if="appStore.sidebarCollapsed" />
        <Fold v-else />
      </el-icon>
    </div>

    <router-link to="/dashboard" class="fm-topbar__brand">
      <div class="mark">F</div>
      <div class="name">FloodMind <span class="ver">v1.0</span></div>
    </router-link>

    <span class="fm-topbar__crumbs">{{ crumbText }}</span>

    <span class="fm-topbar__sp" />

    <div class="fm-topbar__search">
      <el-icon><Search /></el-icon>
      <span class="ph">搜索站点、预案、用户...</span>
      <kbd>⌘K</kbd>
    </div>

    <div class="fm-chip"><span class="ind" />系统运行中</div>
    <div class="fm-chip">{{ nowText }}</div>

    <el-tooltip content="切换主题" placement="bottom">
      <div class="fm-topbar__theme" @click="appStore.toggleDarkMode">
        <el-icon>
          <Moon v-if="appStore.darkMode" />
          <Sunny v-else />
        </el-icon>
      </div>
    </el-tooltip>

    <el-dropdown trigger="click" @command="handleCommand">
      <div class="fm-topbar__avatar">
        <span>{{ avatarChar }}</span>
      </div>
      <template #dropdown>
        <el-dropdown-menu>
          <el-dropdown-item command="profile">个人中心</el-dropdown-item>
          <el-dropdown-item divided command="logout">退出登录</el-dropdown-item>
        </el-dropdown-menu>
      </template>
    </el-dropdown>
  </header>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useAppStore } from '@/stores/app'
import { useUserStore } from '@/stores/user'
import { Search, Moon, Sunny, Expand, Fold } from '@element-plus/icons-vue'

const route = useRoute()
const appStore = useAppStore()
const userStore = useUserStore()

const crumbText = computed(() => {
  const parts = route.matched
    .map((m) => (m.meta?.title as string | undefined))
    .filter(Boolean) as string[]
  return parts.join(' / ')
})

const avatarChar = computed(() => {
  const name = userStore.realName || userStore.username || 'U'
  return name.slice(0, 1).toUpperCase()
})

const nowText = ref('')
let timer: ReturnType<typeof setInterval> | null = null
function tick() {
  const d = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  nowText.value =
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ` +
    `${pad(d.getHours())}:${pad(d.getMinutes())}`
}
onMounted(() => {
  tick()
  timer = setInterval(tick, 30_000)
})
onUnmounted(() => {
  if (timer) clearInterval(timer)
})

function handleCommand(command: string) {
  if (command === 'logout') userStore.logout()
}
</script>

<style scoped lang="scss">
.fm-topbar {
  grid-column: 1 / -1;
  grid-row: 1;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 0 20px;
  height: var(--fm-topbar-h);
  background: linear-gradient(180deg, rgba(17, 26, 44, 0.8), rgba(11, 18, 32, 0.6));
  backdrop-filter: blur(14px);
  border-bottom: 1px solid var(--fm-line);
  z-index: 20;
}

html:not(.dark) .fm-topbar {
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.85), rgba(247, 248, 251, 0.7));
}

.fm-topbar__collapse {
  width: 32px;
  height: 32px;
  display: grid;
  place-items: center;
  border-radius: var(--fm-radius-sm);
  color: var(--fm-fg-mute);
  cursor: pointer;
  font-size: 16px;

  &:hover {
    background: var(--fm-bg-2);
    color: var(--fm-fg);
  }
}

.fm-topbar__brand {
  display: flex;
  align-items: center;
  gap: 10px;
  text-decoration: none;
  color: var(--fm-fg);
  font-weight: 600;

  .mark {
    width: 28px;
    height: 28px;
    border-radius: 8px;
    background: var(--fm-grad-brand);
    box-shadow: 0 0 0 1px rgba(73, 225, 255, 0.3),
      0 8px 20px -6px rgba(47, 123, 255, 0.6);
    display: grid;
    place-items: center;
    font-family: var(--fm-font-mono);
    color: #fff;
    font-size: 14px;
    position: relative;
    overflow: hidden;
  }
  .mark::after {
    content: "";
    position: absolute;
    inset: 0;
    background: radial-gradient(circle at 30% 20%, rgba(255, 255, 255, 0.4), transparent 50%);
  }
  .name {
    font-size: 15px;
  }
  .ver {
    font-family: var(--fm-font-mono);
    font-size: 10px;
    color: var(--fm-fg-mute);
    margin-left: 4px;
  }
}

.fm-topbar__crumbs {
  font-family: var(--fm-font-mono);
  font-size: 11px;
  color: var(--fm-fg-mute);
  letter-spacing: 0.04em;
  padding-left: 6px;
  border-left: 1px solid var(--fm-line);
  margin-left: 4px;
}

.fm-topbar__sp {
  flex: 1;
}

.fm-topbar__search {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 32px;
  padding: 0 12px;
  background: var(--fm-bg-2);
  border: 1px solid var(--fm-line);
  border-radius: var(--fm-radius-sm);
  width: 260px;
  font-size: 12px;
  color: var(--fm-fg-mute);
  cursor: pointer;

  .ph {
    flex: 1;
  }

  kbd {
    font-family: var(--fm-font-mono);
    font-size: 10px;
    padding: 2px 5px;
    border: 1px solid var(--fm-line-2);
    border-radius: 3px;
    color: var(--fm-fg-mute);
    background: var(--fm-bg-3);
  }
}

.fm-topbar__theme {
  width: 32px;
  height: 32px;
  display: grid;
  place-items: center;
  border-radius: var(--fm-radius-sm);
  color: var(--fm-fg-soft);
  cursor: pointer;
  font-size: 15px;

  &:hover {
    background: var(--fm-bg-2);
    color: var(--fm-brand-2);
  }
}

.fm-topbar__avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: linear-gradient(135deg, #2f7bff, #8b5cf6);
  display: grid;
  place-items: center;
  font-size: 12px;
  font-weight: 600;
  color: white;
  box-shadow: 0 0 0 2px var(--fm-bg-1);
  cursor: pointer;

  span {
    pointer-events: none;
  }
}

@media (max-width: 1200px) {
  .fm-topbar__search {
    display: none;
  }
}

@media (max-width: 760px) {
  .fm-topbar {
    gap: 8px;
    padding: 0 10px;
  }

  .fm-topbar__brand .name,
  .fm-topbar__crumbs,
  .fm-chip {
    display: none;
  }
}
</style>
