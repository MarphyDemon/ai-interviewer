import axios from 'axios'
import { detectHost } from '@/utils/bridge'

function getApiBaseURL(): string {
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

const client = axios.create({
  baseURL: getApiBaseURL(),
  timeout: 30000,
})

client.interceptors.request.use((config) => {
  const url = config.url || ''
  const token = url.startsWith('/admin')
    ? localStorage.getItem('admin_token')
    : localStorage.getItem('user_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

client.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const message = error.response?.data?.detail || error.message || '请求失败'
    console.error('[API Error]', message)
    if (error.response?.status === 401) {
      const url = error.config?.url || ''
      if (!url.startsWith('/admin') && !url.startsWith('/auth/')) {
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
