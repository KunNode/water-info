import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { login as loginApi, getMe, logout as logoutApi } from '@/api/auth'
import { getToken, setToken, setRefreshToken, setUserInfo, clearAuth, getUserInfo } from '@/utils/storage'
import type { LoginRequest, UserInfo } from '@/types'
import router from '@/router'

export const useUserStore = defineStore('user', () => {
  const userInfo = ref<UserInfo | null>(getUserInfo<UserInfo>())
  const token = ref<string | null>(getToken())

  const isLoggedIn = computed(() => !!token.value)
  const roles = computed(() => userInfo.value?.roles || [])
  const username = computed(() => userInfo.value?.username || '')
  const realName = computed(() => userInfo.value?.realName || '')

  async function login(data: LoginRequest) {
    const res = await loginApi(data)
    token.value = res.data.accessToken
    userInfo.value = res.data.user
    setToken(res.data.accessToken)
    setRefreshToken(res.data.refreshToken)
    setUserInfo(res.data.user)
    return res
  }

  async function fetchUserInfo() {
    const res = await getMe()
    userInfo.value = res.data
    setUserInfo(res.data)
    return res.data
  }

  async function logout() {
    try {
      await logoutApi()
    } catch {
      // ignore logout API errors
    }
    token.value = null
    userInfo.value = null
    clearAuth()
    router.push('/login')
  }

  function hasRole(role: string | string[]): boolean {
    const required = Array.isArray(role) ? role : [role]
    return required.some((r) => roles.value.includes(r))
  }

  return {
    userInfo,
    token,
    isLoggedIn,
    roles,
    username,
    realName,
    login,
    fetchUserInfo,
    logout,
    hasRole,
  }
})
