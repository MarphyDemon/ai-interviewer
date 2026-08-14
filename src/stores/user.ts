import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { UserInfo } from '@/types'
import * as authApi from '@/api/auth'
import { detectHost } from '@/utils/bridge'

const TOKEN_KEY = 'user_token'

async function getTokenFromStorage(key: string): Promise<string | null> {
  const host = detectHost()
  if (host === 'capacitor') {
    try {
      const { Preferences } = await import('@capacitor/preferences')
      const { value } = await Preferences.get({ key })
      return value
    } catch {
      return localStorage.getItem(key)
    }
  }
  return localStorage.getItem(key)
}

async function setTokenToStorage(key: string, value: string): Promise<void> {
  const host = detectHost()
  if (host === 'capacitor') {
    try {
      const { Preferences } = await import('@capacitor/preferences')
      await Preferences.set({ key, value })
      return
    } catch {
      // fall through to localStorage
    }
  }
  localStorage.setItem(key, value)
}

async function removeTokenFromStorage(key: string): Promise<void> {
  const host = detectHost()
  if (host === 'capacitor') {
    try {
      const { Preferences } = await import('@capacitor/preferences')
      await Preferences.remove({ key })
      return
    } catch {
      // fall through to localStorage
    }
  }
  localStorage.removeItem(key)
}

export const useUserStore = defineStore('user', () => {
  const token = ref<string | null>(localStorage.getItem(TOKEN_KEY))
  const user = ref<UserInfo | null>(null)
  const isLoggedIn = ref(!!token.value)

  async function initTokenFromStorage() {
    const stored = await getTokenFromStorage(TOKEN_KEY)
    if (stored) {
      token.value = stored
      isLoggedIn.value = true
    }
  }

  function setToken(t: string) {
    token.value = t
    isLoggedIn.value = true
    setTokenToStorage(TOKEN_KEY, t)
  }

  function clearToken() {
    token.value = null
    user.value = null
    isLoggedIn.value = false
    removeTokenFromStorage(TOKEN_KEY)
  }

  async function fetchMe() {
    if (!token.value) return null
    try {
      user.value = await authApi.getMe()
      return user.value
    } catch {
      clearToken()
      return null
    }
  }

  async function doLogin(username: string, password: string) {
    const res = await authApi.login(username, password)
    setToken(res.token)
    user.value = res.user
    return res.user
  }

  async function doRegister(username: string, password: string) {
    const res = await authApi.register(username, password)
    setToken(res.token)
    user.value = res.user
    return res.user
  }

  function logout() {
    clearToken()
  }

  return { token, user, isLoggedIn, initTokenFromStorage, setToken, clearToken, fetchMe, doLogin, doRegister, logout }
})
