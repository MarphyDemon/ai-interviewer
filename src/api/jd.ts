import client from './client'
import type { JobDescription } from '@/types'

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
): Promise<JobDescription> {
  const formData = new FormData()
  formData.append('title', title)
  formData.append('content', content)
  if (position) formData.append('position', position)
  return client.post('/jd', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function uploadJd(
  file: File,
  title = '',
  position = '',
): Promise<JobDescription> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('title', title)
  formData.append('position', position)
  return client.post('/jd/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function deleteJd(id: number): Promise<void> {
  return client.delete(`/jd/${id}`)
}
