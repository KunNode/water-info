import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

export type ThemeMode = 'auto' | 'light' | 'dark'

const THEME_KEY = 'fm-theme'

function readPersistedMode(): ThemeMode {
  if (typeof localStorage === 'undefined') return 'dark'
  const v = localStorage.getItem(THEME_KEY)
  if (v === 'auto' || v === 'light' || v === 'dark') return v
  return 'dark'
}

function systemPrefersDark(): boolean {
  if (typeof window === 'undefined' || !window.matchMedia) return true
  return !window.matchMedia('(prefers-color-scheme: light)').matches
}

export const useAppStore = defineStore('app', () => {
  const sidebarCollapsed = ref(false)
  const themeMode = ref<ThemeMode>(readPersistedMode())
  const systemDark = ref(systemPrefersDark())
  const tagsViewVisible = ref(true)

  const visitedViews = ref<Array<{ path: string; name: string; title: string }>>([])

  const darkMode = computed(() =>
    themeMode.value === 'auto' ? systemDark.value : themeMode.value === 'dark',
  )

  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }

  function applyTheme() {
    document.documentElement.classList.toggle('dark', darkMode.value)
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(THEME_KEY, themeMode.value)
    }
  }

  function setThemeMode(mode: ThemeMode) {
    themeMode.value = mode
    applyTheme()
  }

  // Cycle: auto → light → dark → auto. Kept for keyboard / accessibility paths.
  function toggleDarkMode() {
    const next: ThemeMode =
      themeMode.value === 'auto' ? 'light' : themeMode.value === 'light' ? 'dark' : 'auto'
    setThemeMode(next)
  }

  let mqlBound = false
  function watchSystemTheme() {
    if (mqlBound || typeof window === 'undefined' || !window.matchMedia) return
    const mql = window.matchMedia('(prefers-color-scheme: light)')
    const onChange = (e: MediaQueryListEvent | MediaQueryList) => {
      systemDark.value = !e.matches
      if (themeMode.value === 'auto') applyTheme()
    }
    if (typeof mql.addEventListener === 'function') {
      mql.addEventListener('change', onChange as (e: MediaQueryListEvent) => void)
    } else {
      // Safari < 14 fallback
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      ;(mql as unknown as { addListener: (fn: (e: MediaQueryListEvent) => void) => void }).addListener(
        onChange as (e: MediaQueryListEvent) => void,
      )
    }
    mqlBound = true
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
    themeMode,
    darkMode,
    tagsViewVisible,
    visitedViews,
    toggleSidebar,
    setThemeMode,
    toggleDarkMode,
    applyTheme,
    watchSystemTheme,
    addVisitedView,
    removeVisitedView,
    clearVisitedViews,
  }
})
