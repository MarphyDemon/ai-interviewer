import client from './client'
import type { ResumeInfo } from '@/types'

export interface ResumeReportData {
  grade: string
  structureScore: number
  positionMatch: number
  skillCoverage: number
  projectDepth: number
  highlights: string[]
  weaknesses: string[]
  improvements: Array<{ section: string; suggestion: string }>
  recommendedPositions: string[]
}

export interface ResumeReport {
  id: number
  resumeId: number
  position: string
  grade: string
  data: ResumeReportData
  createdAt: string
}

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

export function generateResumeReport(
  resumeId: number,
  position: string,
): Promise<ResumeReport> {
  return client.post(`/resume/${resumeId}/report`, { position })
}

export function getResumeReport(
  resumeId: number,
  position: string,
): Promise<ResumeReport> {
  return client.get(`/resume/${resumeId}/report`, { params: { position } })
}

export async function downloadResumeReportPdf(
  resumeId: number,
  position: string,
): Promise<void> {
  const params = new URLSearchParams({ position })
  const response = await fetch(
    `${import.meta.env.VITE_API_BASE_URL || '/api'}/resume/${resumeId}/report/pdf?${params}`,
  )
  if (!response.ok) throw new Error('PDF 导出失败')
  const blob = await response.blob()
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `resume_report_${resumeId}.pdf`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  window.URL.revokeObjectURL(url)
}
