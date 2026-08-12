import client from './client'
import type { KnowledgeDoc } from '@/types'

export function uploadKnowledge(files: File[]): Promise<{ ids: number[] }> {
  const formData = new FormData()
  files.forEach((file) => formData.append('files', file))
  return client.post('/knowledge/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function getKnowledgeList(): Promise<KnowledgeDoc[]> {
  return client.get('/knowledge')
}

export function getKnowledgeStatus(id: number): Promise<{ status: string }> {
  return client.get(`/knowledge/${id}/status`)
}

export function deleteKnowledge(id: number): Promise<void> {
  return client.delete(`/knowledge/${id}`)
}
