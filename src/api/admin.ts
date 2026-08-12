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
