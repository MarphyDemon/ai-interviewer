import client from './client'
import type { AvatarConfig } from '@/types'

export function getAvatarConfig(): Promise<AvatarConfig> {
  return client.get('/avatar/config')
}

export interface AvatarItem {
  id: number
  name: string
  coverUrl: string
  extra: { emoji?: string; color?: string; [k: string]: unknown }
}

export function getAvatarList(): Promise<AvatarItem[]> {
  return client.get('/avatar/list')
}

export function setPreferredAvatar(
  avatarId: number,
): Promise<{ ok: boolean; preferredAvatarId: number }> {
  return client.put('/avatar/preference', { avatarId })
}
