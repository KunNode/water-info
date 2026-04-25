<template>
  <div class="fm-shell" :class="{ collapsed: appStore.sidebarCollapsed }">
    <Header />
    <Sidebar />
    <main class="fm-main">
      <TagsView />
      <div class="fm-main__body">
        <router-view v-slot="{ Component }">
          <transition name="fade-transform" mode="out-in">
            <keep-alive :max="10">
              <component :is="Component" />
            </keep-alive>
          </transition>
        </router-view>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { useAppStore } from '@/stores/app'
import Sidebar from './components/Sidebar.vue'
import Header from './components/Header.vue'
import TagsView from './components/TagsView.vue'

const appStore = useAppStore()
</script>

<style scoped lang="scss">
.fm-shell {
  display: grid;
  grid-template-columns: var(--fm-sidebar-w) 1fr;
  grid-template-rows: var(--fm-topbar-h) 1fr;
  height: 100vh;
  overflow: hidden;
  transition: grid-template-columns 0.2s ease;

  &.collapsed {
    grid-template-columns: var(--fm-sidebar-w-collapsed) 1fr;
  }
}

.fm-main {
  grid-column: 2;
  grid-row: 2;
  position: relative;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  height: 100%;

  &::before {
    content: "";
    position: absolute;
    inset: 0;
    background: var(--fm-grad-hero);
    pointer-events: none;
    z-index: 0;
  }

  > :deep(*) {
    position: relative;
    z-index: 1;
  }
}

.fm-main__body {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 22px 26px 60px;
}

.fade-transform-enter-active,
.fade-transform-leave-active {
  transition: all 0.2s;
}
.fade-transform-enter-from {
  opacity: 0;
  transform: translateX(-10px);
}
.fade-transform-leave-to {
  opacity: 0;
  transform: translateX(10px);
}

@media (max-width: 760px) {
  .fm-shell,
  .fm-shell.collapsed {
    grid-template-columns: var(--fm-sidebar-w-collapsed) 1fr;
  }

  .fm-main__body {
    padding: 16px 12px 42px;
  }
}
</style>
