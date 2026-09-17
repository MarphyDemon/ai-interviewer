import client from './client'
import type { ProfileSummary } from '@/types'

/** 跨会话面试画像：往期场次、平均分、反复出现的薄弱点 */
export function getProfileSummary(limit = 8): Promise<ProfileSummary> {
  return client.get('/profile/summary', { params: { limit } })
}
