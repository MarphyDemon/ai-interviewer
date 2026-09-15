import client from './client'
import type { LLMConfig } from '@/types'

export function verifyAdmin(password: string): Promise<{ token: string }> {
  return client.post('/admin/verify', { password })
}

export function getLLMConfigs(): Promise<LLMConfig[]> {
  return client.get('/admin/llm-config')
}

export function createLLMConfig(data: {
  name: string
  baseUrl: string
  apiKey: string
  model: string
}): Promise<LLMConfig> {
  return client.post('/admin/llm-config', data)
}

export function updateLLMConfig(
  id: number,
  data: { name?: string; baseUrl?: string; apiKey?: string; model?: string },
): Promise<LLMConfig> {
  return client.put(`/admin/llm-config/${id}`, data)
}

export function activateLLMConfig(id: number): Promise<void> {
  return client.post(`/admin/llm-config/${id}/activate`)
}

export function deactivateLLMConfig(id: number): Promise<void> {
  return client.post(`/admin/llm-config/${id}/deactivate`)
}

export function deleteLLMConfig(id: number): Promise<void> {
  return client.delete(`/admin/llm-config/${id}`)
}

// ---------- 具身交互智能体服务凭证（AvatarProviderConfig）----------

export interface AvatarProviderConfigItem {
  id: number
  name: string
  appId: string
  appSecretMasked: string
  gatewayServer: string
  avatarImage: string
  isActive: boolean
}

export function getAvatarConfigs(): Promise<AvatarProviderConfigItem[]> {
  return client.get('/admin/avatar-config')
}

export function createAvatarConfig(data: {
  name: string
  appId: string
  appSecret: string
  gatewayServer: string
  avatarImage?: string
}): Promise<{ id: number; name: string }> {
  return client.post('/admin/avatar-config', data)
}

export function updateAvatarConfig(
  id: number,
  data: { name?: string; appId?: string; appSecret?: string; gatewayServer?: string; avatarImage?: string },
): Promise<void> {
  return client.put(`/admin/avatar-config/${id}`, data)
}

export function activateAvatarConfig(id: number): Promise<void> {
  return client.post(`/admin/avatar-config/${id}/activate`)
}

export function deactivateAvatarConfig(id: number): Promise<void> {
  return client.post(`/admin/avatar-config/${id}/deactivate`)
}

export function deleteAvatarConfig(id: number): Promise<void> {
  return client.delete(`/admin/avatar-config/${id}`)
}

export interface BrainVerifyResult {
  brain_config: {
    provider: string
    base_url: string
    model: string
    api_key_preview: string
  }
  token: {
    token_preview: string
    conversation_id: number
    ttl_hours: number
  }
  rag: {
    knowledge_found: boolean
    knowledge_preview: string
  }
  llm: {
    ok: boolean
    model: string
    reply_preview: string
    error: string | null
  }
}

export function brainVerify(message?: string): Promise<BrainVerifyResult> {
  return client.post('/avatar/brain-verify', { message: message || '你好，请做个自我介绍' })
}

// ---------- 用户管理（P2 新增）----------

export interface UserListItem {
  id: number
  username: string
  role: 'user' | 'admin'
  createdAt: string
  plan: 'free' | 'standard' | 'enterprise'
}

export function getUsers(): Promise<UserListItem[]> {
  return client.get('/admin/users')
}

export function promoteUser(userId: number, role: string): Promise<{ ok: boolean; role: string }> {
  return client.post(`/admin/users/${userId}/promote`, { role })
}

export function setUserQuota(userId: number, data: {
  plan?: string
  interviewLimit?: number
  knowledgeLimit?: number
  aiCallsLimit?: number
}): Promise<{ ok: boolean }> {
  return client.post(`/admin/users/${userId}/quota`, data)
}

// ---------- 平台统计（P4 新增）----------

export interface PlatformStats {
  totalUsers: number
  totalAdmins: number
  totalInterviews: number
  totalReports: number
  totalKnowledgeDocs: number
  totalKnowledgeVersions: number
  freePlanUsers: number
  standardPlanUsers: number
  enterprisePlanUsers: number
}

export function getPlatformStats(): Promise<PlatformStats> {
  return client.get('/admin/stats')
}

// ---------- 邀请码管理（P4 新增）----------

export interface InviteCodeItem {
  id: number
  code: string
  plan: string
  maxUses: number
  usedCount: number
  isActive: boolean
  expiresAt: string | null
  note: string | null
  createdAt: string | null
}

export function getInviteCodes(): Promise<InviteCodeItem[]> {
  return client.get('/admin/invite-codes')
}

export function createInviteCode(data: {
  plan?: string
  maxUses?: number
  note?: string
}): Promise<{ id: number; code: string }> {
  return client.post('/admin/invite-codes', data)
}

export function redeemInviteCode(code: string): Promise<{ ok: boolean; plan: string }> {
  return client.post(`/admin/invite-codes/${code}/redeem`)
}
