import client from './client'
import type { AvatarConfig } from '@/types'

export function getAvatarConfig(): Promise<AvatarConfig> {
  return client.get('/avatar/config')
}

export interface HomepageAvatarItem {
  id: number | null
  name: string
  avatarImage: string
  isDefault: boolean
  isSelected: boolean
}

export function getHomepageAvatars(): Promise<HomepageAvatarItem[]> {
  return client.get('/avatar/homepage-avatars')
}

export function setPreferredAvatar(
  avatarConfigId: number | null,
): Promise<{ ok: boolean; preferredAvatarConfigId: number | null }> {
  return client.put('/avatar/preference', { avatarConfigId })
}
