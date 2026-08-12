import client from './client'
import type { ResumeInfo } from '@/types'

export function uploadResume(
  file: File,
  position: string,
): Promise<ResumeInfo> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('position', position)
  return client.post('/resume/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function getResumeList(): Promise<ResumeInfo[]> {
  return client.get('/resume')
}

export function getResume(id: number): Promise<ResumeInfo> {
  return client.get(`/resume/${id}`)
}

export function deleteResume(id: number): Promise<void> {
  return client.delete(`/resume/${id}`)
}
