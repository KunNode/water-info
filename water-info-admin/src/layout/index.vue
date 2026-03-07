<template>
  <el-container class="layout-container">
    <Sidebar />
    <el-container class="main-container" :style="{ marginLeft: sidebarWidth }">
      <Header />
      <TagsView />
      <el-main class="main-content">
        <router-view v-slot="{ Component }">
          <transition name="fade-transform" mode="out-in">
            <keep-alive :max="10">
              <component :is="Component" />
            </keep-alive>
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useAppStore } from '@/stores/app'
import Sidebar from './components/Sidebar.vue'
import Header from './components/Header.vue'
import TagsView from './components/TagsView.vue'

const appStore = useAppStore()
const sidebarWidth = computed(() => (appStore.sidebarCollapsed ? '64px' : '210px'))
</script>

<style scoped lang="scss">
.layout-container {
  height: 100vh;
  width: 100%;
}

.main-container {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  transition: margin-left 0.28s;
}

.main-content {
  background-color: #f0f2f5;
  padding: 0;
  overflow-y: auto;
  flex: 1;
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

html.dark .main-content {
  background-color: #141414;
}
</style>
