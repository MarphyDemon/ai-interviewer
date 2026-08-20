import client from './client'
import type { AvatarConfig, BrainConfig } from '@/types'

export function getAvatarConfig(): Promise<AvatarConfig> {
  return client.get('/avatar/config')
}

export function getBrainConfig(conversationId?: number): Promise<BrainConfig> {
  const params = conversationId ? `?conversation_id=${conversationId}` : ''
  return client.get(`/avatar/brain-config${params}`)
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
