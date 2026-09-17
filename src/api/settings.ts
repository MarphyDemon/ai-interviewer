import client from './client'
import type { NotificationSettings, UserQuota, NotificationItem } from '@/types'

export interface PersonalSettingsResponse {
  preferredAvatarConfigId: number | null
  preferredPosition: string
  language: 'zh' | 'en'
  theme: 'light' | 'dark'
  notificationSettings: NotificationSettings
  quota: UserQuota
}

export interface RuntimeModeResponse {
  /** cloud=云端凭证 ｜ local-llm=本地 Ollama ｜ offline=离线规则模式 ｜ unconfigured=未配置 */
  mode: 'cloud' | 'local-llm' | 'offline' | 'unconfigured'
  llmModel: string
  embeddingProvider: string
  avatarConfigured: boolean
}

/** 当前运行模式（无凭证部署时，前端据此提示能力边界） */
export function getRuntimeMode(): Promise<RuntimeModeResponse> {
  return client.get('/mode')
}

export function getPersonalSettings(): Promise<PersonalSettingsResponse> {
  return client.get('/settings/personal')
}

export function updatePersonalSettings(data: {
  preferredAvatarConfigId?: number | null
  preferredPosition?: string
  language?: 'zh' | 'en'
  theme?: 'light' | 'dark'
  notificationSettings?: NotificationSettings
}): Promise<{ ok: boolean }> {
  return client.put('/settings/personal', data)
}

export function getNotifications(): Promise<NotificationItem[]> {
  return client.get('/settings/notifications')
}

export function markNotificationRead(nid: number): Promise<{ ok: boolean }> {
  return client.post(`/settings/notifications/${nid}/read`)
}

export function markAllNotificationsRead(): Promise<{ ok: boolean; count: number }> {
  return client.post('/settings/notifications/read-all')
}