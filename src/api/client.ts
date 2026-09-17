import axios from 'axios'
import { detectHost } from '@/utils/bridge'

/** 后端 API 基址（已含 /api 后缀）。导出供 EventSource 等非 axios 场景复用。 */
export function getApiBaseURL(): string {
  const host = detectHost()
  const envBase = import.meta.env.VITE_API_BASE_URL
  if (envBase) {
    return envBase.replace(/\/$/, '') + '/api'
  }
  if (host === 'capacitor' && import.meta.env.DEV) {
    return 'http://localhost:8000/api'
  }
  return '/api'
}

/** 读取登录 token。导出供 EventSource 等非 axios 场景复用。 */
export async function getToken(url = ''): Promise<string | null> {
  const isAdminUrl = url.startsWith('/admin')
  const tokenKey = isAdminUrl ? 'admin_token' : 'user_token'
  const host = detectHost()

  const read = async (key: string): Promise<string | null> => {
    if (host === 'capacitor') {
      try {
        const { Preferences } = await import('@capacitor/preferences')
        const { value } = await Preferences.get({ key })
        if (value) return value
      } catch {
        // Fall back to localStorage
      }
    }
    return localStorage.getItem(key)
  }

  const token = await read(tokenKey)
  if (token) return token
  // 管理接口：口令 token 缺失时回退到已登录的管理员用户 token（role=admin）
  if (isAdminUrl) return read('user_token')
  return null
}

const client = axios.create({
  baseURL: getApiBaseURL(),
  timeout: 30000,
})

client.interceptors.request.use(async (config) => {
  const url = config.url || ''
  const token = await getToken(url)
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

/** 管理口令 token 失效时通知 AdminView 回退到口令校验界面 */
export const ADMIN_UNAUTHORIZED_EVENT = 'admin-unauthorized'

client.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const message = error.response?.data?.detail || error.message || '请求失败'
    console.error('[API Error]', message)
    if (error.response?.status === 401) {
      const url = error.config?.url || ''
      if (url.startsWith('/admin')) {
        // /admin/verify 是口令校验本身（失败返回 403），不参与失效回退
        if (!url.startsWith('/admin/verify')) {
          localStorage.removeItem('admin_token')
          if (typeof window !== 'undefined') {
            window.dispatchEvent(new Event(ADMIN_UNAUTHORIZED_EVENT))
          }
        }
      } else if (!url.startsWith('/auth/')) {
        localStorage.removeItem('user_token')
        if (typeof window !== 'undefined' && window.location.pathname !== '/login') {
          window.location.href = `/login?redirect=${encodeURIComponent(window.location.pathname)}`
        }
      }
    }
    return Promise.reject(new Error(message))
  },
)

export default client
