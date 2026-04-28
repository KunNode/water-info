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
  height: var(--fm-tags-h);
  background: var(--fm-bg-1);
  border-bottom: 1px solid var(--fm-line);
}

.tags-wrapper {
  display: flex;
  align-items: center;
  padding: 0 10px;
  height: var(--fm-tags-h);
  gap: 6px;
}

.tag-item {
  display: inline-flex;
  align-items: center;
  height: 24px;
  padding: 0 10px;
  font-size: 11.5px;
  font-family: var(--fm-font-mono);
  letter-spacing: 0.02em;
  color: var(--fm-fg-soft);
  background: var(--fm-bg-2);
  border: 1px solid var(--fm-line);
  border-radius: 12px;
  white-space: nowrap;
  cursor: pointer;
  text-decoration: none;
  transition: all 0.15s ease;

  &:hover {
    color: var(--fm-fg);
    border-color: var(--fm-line-2);
  }

  &.active {
    background: linear-gradient(90deg, rgba(47, 123, 255, 0.22), rgba(73, 225, 255, 0.08));
    color: var(--fm-fg);
    border-color: rgba(73, 225, 255, 0.4);
    box-shadow: 0 0 0 1px rgba(73, 225, 255, 0.2), 0 0 12px -4px var(--fm-brand-glow);
  }

  .tag-close {
    margin-left: 6px;
    font-size: 11px;
    border-radius: 50%;

    &:hover {
      background-color: rgba(255, 255, 255, 0.12);
      color: var(--fm-fg);
    }
  }
}
</style>
