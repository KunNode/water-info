import { defineStore } from 'pinia'
import { ref } from 'vue'

// FloodMind defaults to a dark command-center theme. Persist the user's
// preference in localStorage so reloads don't flash back to dark.
const THEME_KEY = 'fm-theme'
function readPersistedDark(): boolean {
  if (typeof localStorage === 'undefined') return true
  const v = localStorage.getItem(THEME_KEY)
  if (v === 'light') return false
  if (v === 'dark') return true
  return true
}

export const useAppStore = defineStore('app', () => {
  const sidebarCollapsed = ref(false)
  const darkMode = ref(readPersistedDark())
  const tagsViewVisible = ref(true)

  // Tags view (visited pages)
  const visitedViews = ref<Array<{ path: string; name: string; title: string }>>([])

  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }

  function applyTheme() {
    document.documentElement.classList.toggle('dark', darkMode.value)
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(THEME_KEY, darkMode.value ? 'dark' : 'light')
    }
  }

  function toggleDarkMode() {
    darkMode.value = !darkMode.value
    applyTheme()
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
    applyTheme,
    addVisitedView,
    removeVisitedView,
    clearVisitedViews,
  }
})
