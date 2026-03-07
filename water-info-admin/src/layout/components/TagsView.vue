<template>
  <div v-if="appStore.tagsViewVisible" class="tags-view">
    <el-scrollbar>
      <div class="tags-wrapper">
        <router-link
          v-for="tag in visitedViews"
          :key="tag.path"
          :to="tag.path"
          class="tag-item"
          :class="{ active: isActive(tag) }"
        >
          {{ tag.title }}
          <el-icon v-if="!tag.path.includes('dashboard')" class="tag-close" @click.prevent.stop="closeTag(tag)">
            <Close />
          </el-icon>
        </router-link>
      </div>
    </el-scrollbar>
  </div>
</template>

<script setup lang="ts">
import { watch } from 'vue'
import { useRoute } from 'vue-router'
import { useAppStore } from '@/stores/app'
import { Close } from '@element-plus/icons-vue'
import { computed } from 'vue'
import router from '@/router'

const route = useRoute()
const appStore = useAppStore()

const visitedViews = computed(() => appStore.visitedViews)

function isActive(tag: { path: string }) {
  return tag.path === route.path
}

function closeTag(tag: { path: string }) {
  appStore.removeVisitedView(tag.path)
  if (isActive(tag)) {
    const lastView = visitedViews.value[visitedViews.value.length - 1]
    router.push(lastView ? lastView.path : '/dashboard')
  }
}

watch(
  route,
  (to) => {
    if (to.meta?.title && to.name) {
      appStore.addVisitedView({
        path: to.path,
        name: to.name as string,
        title: to.meta.title as string,
      })
    }
  },
  { immediate: true },
)
</script>

<style scoped lang="scss">
.tags-view {
  height: 34px;
  background: #fff;
  border-bottom: 1px solid #d8dce5;
  box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.04);
}

html.dark .tags-view {
  background: #1d1e1f;
  border-bottom-color: #414243;
}

.tags-wrapper {
  display: flex;
  align-items: center;
  padding: 0 8px;
  height: 34px;
  gap: 4px;
}

.tag-item {
  display: inline-flex;
  align-items: center;
  height: 26px;
  padding: 0 10px;
  font-size: 12px;
  color: #495060;
  background: #fff;
  border: 1px solid #d8dce5;
  border-radius: 3px;
  white-space: nowrap;
  cursor: pointer;
  text-decoration: none;

  &.active {
    background-color: #409eff;
    color: #fff;
    border-color: #409eff;
  }

  .tag-close {
    margin-left: 4px;
    font-size: 12px;
    border-radius: 50%;

    &:hover {
      background-color: rgba(0, 0, 0, 0.15);
      color: #fff;
    }
  }
}
</style>
