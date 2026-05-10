const REMEMBER_USER_KEY = 'water_remember_user'
const REMEMBER_PASS_KEY = 'water_remember_pass'
const TOKEN_KEY = 'water_access_token'
const REFRESH_TOKEN_KEY = 'water_refresh_token'
const USER_KEY = 'water_user_info'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function removeToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_TOKEN_KEY)
}

export function setRefreshToken(token: string): void {
  localStorage.setItem(REFRESH_TOKEN_KEY, token)
}

export function removeRefreshToken(): void {
  localStorage.removeItem(REFRESH_TOKEN_KEY)
}

export function getUserInfo<T = any>(): T | null {
  const raw = localStorage.getItem(USER_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as T
  } catch {
    return null
  }
}

export function setUserInfo(info: any): void {
  localStorage.setItem(USER_KEY, JSON.stringify(info))
}

export function removeUserInfo(): void {
  localStorage.removeItem(USER_KEY)
}

export function clearAuth(): void {
  removeToken()
  removeRefreshToken()
  removeUserInfo()
}

export function getRememberedUsername(): string | null {
  return localStorage.getItem(REMEMBER_USER_KEY)
}

export function getRememberedPassword(): string | null {
  return localStorage.getItem(REMEMBER_PASS_KEY)
}

export function setRememberedCredentials(username: string, password: string): void {
  localStorage.setItem(REMEMBER_USER_KEY, username)
  localStorage.setItem(REMEMBER_PASS_KEY, password)
}

export function clearRememberedCredentials(): void {
  localStorage.removeItem(REMEMBER_USER_KEY)
  localStorage.removeItem(REMEMBER_PASS_KEY)
}
