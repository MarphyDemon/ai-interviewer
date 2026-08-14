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

// ---------- 数字人服务凭证（AvatarProviderConfig）----------

export interface AvatarProviderConfigItem {
  id: number
  name: string
  appId: string
  appSecretMasked: string
  gatewayServer: string
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
}): Promise<{ id: number; name: string }> {
  return client.post('/admin/avatar-config', data)
}

export function updateAvatarConfig(
  id: number,
  data: { name?: string; appId?: string; appSecret?: string; gatewayServer?: string },
): Promise<void> {
  return client.put(`/admin/avatar-config/${id}`, data)
}

export function activateAvatarConfig(id: number): Promise<void> {
  return client.post(`/admin/avatar-config/${id}/activate`)
}

export function deleteAvatarConfig(id: number): Promise<void> {
  return client.delete(`/admin/avatar-config/${id}`)
}
