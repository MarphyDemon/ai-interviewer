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