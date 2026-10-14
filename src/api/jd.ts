import client from './client'
import type { JobDescription } from '@/types'

/** 资源作用域：personal=个人私有；org=企业组织共享（同组织成员可见） */
export type JdScope = 'personal' | 'org'

export function listJds(): Promise<JobDescription[]> {
  return client.get('/jd')
}

export function getJd(id: number): Promise<JobDescription> {
  return client.get(`/jd/${id}`)
}

export function createJd(
  title: string,
  content: string,
  position = '',
  scope: JdScope = 'personal',
): Promise<JobDescription> {
  const formData = new FormData()
  formData.append('title', title)
  formData.append('content', content)
  if (position) formData.append('position', position)
  formData.append('scope', scope)
  return client.post('/jd', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function uploadJd(
  file: File,
  title = '',
  position = '',
  scope: JdScope = 'personal',
): Promise<JobDescription> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('title', title)
  formData.append('position', position)
  formData.append('scope', scope)
  return client.post('/jd/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function updateJd(
  id: number,
  payload: { title?: string; content?: string; position?: string },
): Promise<JobDescription> {
  const formData = new FormData()
  if (payload.title !== undefined) formData.append('title', payload.title)
  if (payload.content !== undefined) formData.append('content', payload.content)
  if (payload.position !== undefined) formData.append('position', payload.position)
  return client.put(`/jd/${id}`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function deleteJd(id: number): Promise<void> {
  return client.delete(`/jd/${id}`)
}
