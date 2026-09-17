import client from './client'
import type { InterviewMetricRow, MetricsSummary } from '@/types'

/** 实测指标聚合（首字延迟 / 工具耗时 / 端到端 / 打断延迟） */
export function getMetricsSummary(
  days = 30,
  scope: 'me' | 'all' = 'me',
): Promise<MetricsSummary> {
  return client.get('/metrics/summary', { params: { days, scope } })
}

/** 每次面试的指标明细 */
export function getInterviewMetrics(
  limit = 50,
  scope: 'me' | 'all' = 'me',
): Promise<InterviewMetricRow[]> {
  return client.get('/metrics/interviews', { params: { limit, scope } })
}
