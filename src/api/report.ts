import client from './client'
import type { ReportData } from '@/types'

export function getReport(interviewId: number): Promise<ReportData> {
  return client.get(`/report/${interviewId}`)
}
