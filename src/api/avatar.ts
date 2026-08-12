import client from './client'
import type { AvatarConfig } from '@/types'

export function getAvatarConfig(): Promise<AvatarConfig> {
  return client.get('/avatar/config')
}
