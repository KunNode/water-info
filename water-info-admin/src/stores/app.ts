import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAppStore = defineStore('app', () => {
  const sidebarCollapsed = ref(false)
  const darkMode = ref(false)
  const tagsViewVisible = ref(true)

  // Tags view (visited pages)
  const visitedViews = ref<Array<{ path: string; name: string; title: string }>>([])

  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }

  function toggleDarkMode() {
    darkMode.value = !darkMode.value
    document.documentElement.classList.toggle('dark', darkMode.value)
  }

  function addVisitedView(view: { path: string; name: string; title: string }) {
    if (visitedViews.value.some((v) => v.path === view.path)) return
    visitedViews.value.push(view)
  }

  function removeVisitedView(path: string) {
    const idx = visitedViews.value.findIndex((v) => v.path === path)
    if (idx > -1) visitedViews.value.splice(idx, 1)
  }

  function clearVisitedViews() {
    visitedViews.value = []
  }

  return {
    sidebarCollapsed,
    darkMode,
    tagsViewVisible,
    visitedViews,
    toggleSidebar,
    toggleDarkMode,
    addVisitedView,
    removeVisitedView,
    clearVisitedViews,
  }
})
