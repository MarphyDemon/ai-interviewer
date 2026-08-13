import client from './client'
import type { ReportData } from '@/types'

export function getReport(interviewId: number): Promise<ReportData> {
  return client.get(`/report/${interviewId}`)
}

export async function downloadReportPdf(interviewId: number): Promise<void> {
  const response = await fetch(
    `${import.meta.env.VITE_API_BASE_URL || '/api'}/report/${interviewId}/pdf`
  )
  if (!response.ok) throw new Error('PDF 导出失败')
  const blob = await response.blob()
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `interview_report_${interviewId}.pdf`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  window.URL.revokeObjectURL(url)
}
