import client from './client'
import type { KnowledgeDoc, KnowledgeVersionInfo, KnowledgeVersionDetail, CollaboratorInfo } from '@/types'

/** 上传作用域：personal=个人知识库；org=企业知识库（全组织共享） */
export type KnowledgeScope = 'personal' | 'org'

export function uploadKnowledge(
  files: File[],
  scope: KnowledgeScope = 'personal',
): Promise<{ ids: number[] }> {
  const formData = new FormData()
  files.forEach((file) => formData.append('files', file))
  formData.append('scope', scope)
  return client.post('/knowledge/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function getKnowledgeList(): Promise<KnowledgeDoc[]> {
  return client.get('/knowledge')
}

export function getPositions(): Promise<{ positions: string[] }> {
  return client.get('/knowledge/positions')
}

export function getKnowledgeStatus(id: number): Promise<{ status: string }> {
  return client.get(`/knowledge/${id}/status`)
}

export function deleteKnowledge(id: number): Promise<void> {
  return client.delete(`/knowledge/${id}`)
}

// 版本管理
export function getKnowledgeVersions(docId: number): Promise<KnowledgeVersionInfo[]> {
  return client.get(`/knowledge/${docId}/versions`)
}

export function getKnowledgeVersion(docId: number, versionId: number): Promise<KnowledgeVersionDetail> {
  return client.get(`/knowledge/${docId}/versions/${versionId}`)
}

export function createKnowledgeVersion(docId: number, changeNote: string): Promise<{ id: number; versionNumber: number }> {
  return client.post(`/knowledge/${docId}/versions`, { changeNote })
}

export function rollbackKnowledgeVersion(docId: number, versionId: number): Promise<{ ok: boolean; newVersion: number }> {
  return client.post(`/knowledge/${docId}/versions/${versionId}/rollback`)
}

export function deleteKnowledgeVersion(docId: number, versionId: number): Promise<void> {
  return client.delete(`/knowledge/${docId}/versions/${versionId}`)
}

// 协作锁
export function acquireEditLock(docId: number): Promise<{ locked: boolean; lockId: number | null }> {
  return client.post(`/knowledge/${docId}/lock`)
}

export function releaseEditLock(docId: number): Promise<{ ok: boolean }> {
  return client.post(`/knowledge/${docId}/unlock`)
}

// 协作者管理
export function getCollaborators(docId: number): Promise<CollaboratorInfo[]> {
  return client.get(`/knowledge/${docId}/collaborators`)
}

export function addCollaborator(docId: number, userId: number, permission: string): Promise<{ ok: boolean }> {
  return client.post(`/knowledge/${docId}/collaborators`, { userId, permission })
}

export function removeCollaborator(docId: number, collabId: number): Promise<{ ok: boolean }> {
  return client.delete(`/knowledge/${docId}/collaborators/${collabId}`)
}