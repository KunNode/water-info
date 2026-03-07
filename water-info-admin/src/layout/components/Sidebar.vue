<template>
  <el-aside :width="sidebarWidth" class="sidebar">
    <div class="logo-container">
      <img src="/vite.svg" alt="logo" class="logo-img" />
      <span v-show="!collapsed" class="logo-text">智慧水利</span>
    </div>
    <el-scrollbar>
      <el-menu
        :default-active="activeMenu"
        :collapse="collapsed"
        :unique-opened="true"
        background-color="#001529"
        text-color="#bfcbd9"
        active-text-color="#409eff"
        router
      >
        <template v-for="route in menuRoutes" :key="route.path">
          <!-- Single child or top-level -->
          <template v-if="route.children && route.children.length === 1">
            <el-menu-item :index="resolvePath(route, route.children[0])">
              <el-icon><component :is="route.children[0].meta?.icon || route.meta?.icon" /></el-icon>
              <template #title>{{ route.children[0].meta?.title || route.meta?.title }}</template>
            </el-menu-item>
          </template>

          <!-- Multiple children — submenu -->
          <el-sub-menu v-else-if="route.children && route.children.length > 1" :index="route.path">
            <template #title>
              <el-icon><component :is="route.meta?.icon" /></el-icon>
              <span>{{ route.meta?.title }}</span>
            </template>
            <el-menu-item
              v-for="child in visibleChildren(route)"
              :key="child.path"
              :index="resolvePath(route, child)"
            >
              <el-icon><component :is="child.meta?.icon" /></el-icon>
              <template #title>{{ child.meta?.title }}</template>
            </el-menu-item>
          </el-sub-menu>
        </template>
      </el-menu>
    </el-scrollbar>
  </el-aside>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, type RouteRecordRaw } from 'vue-router'
import { useAppStore } from '@/stores/app'
import { useUserStore } from '@/stores/user'
import { constantRoutes } from '@/router'
import { canAccess } from '@/utils/permission'

const route = useRoute()
const appStore = useAppStore()
const userStore = useUserStore()

const collapsed = computed(() => appStore.sidebarCollapsed)
const sidebarWidth = computed(() => (collapsed.value ? '64px' : '210px'))
const activeMenu = computed(() => route.path)

const menuRoutes = computed(() => {
  return constantRoutes.filter((r) => {
    if (r.meta?.hidden) return false
    if (!r.children) return false
    // Check parent role requirement
    if (r.meta?.roles && !canAccess(userStore.roles, r.meta.roles as string[])) return false
    return true
  })
})

function visibleChildren(parent: RouteRecordRaw) {
  return (parent.children || []).filter((child) => {
    if (child.meta?.hidden) return false
    if (child.meta?.roles && !canAccess(userStore.roles, child.meta.roles as string[])) return false
    return true
  })
}

function resolvePath(parent: RouteRecordRaw, child: RouteRecordRaw): string {
  if (child.path.startsWith('/')) return child.path
  const base = parent.path.endsWith('/') ? parent.path : parent.path + '/'
  return base + child.path
}
</script>

<style scoped lang="scss">
.sidebar {
  position: fixed;
  top: 0;
  left: 0;
  bottom: 0;
  z-index: 1001;
  background-color: #001529;
  overflow: hidden;
  transition: width 0.28s;
}

.logo-container {
  height: 50px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 16px;
  background-color: #002140;

  .logo-img {
    width: 28px;
    height: 28px;
  }

  .logo-text {
    margin-left: 10px;
    font-size: 16px;
    font-weight: 600;
    color: #fff;
    white-space: nowrap;
  }
}

:deep(.el-menu) {
  border-right: none;
}
</style>
