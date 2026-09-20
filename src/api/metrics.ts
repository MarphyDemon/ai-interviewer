import client from './client'
import type { InterviewMetricRow, MetricsSummary } from '@/types'

/**
 * 实测指标聚合（首字延迟 / 工具耗时 / 端到端 / 打断延迟）。
 * 该页面仅平台管理员可见，默认取全站数据（scope=all）。
 */
export function getMetricsSummary(
  days = 30,
  scope: 'me' | 'all' = 'all',
): Promise<MetricsSummary> {
  return client.get('/metrics/summary', { params: { days, scope } })
}

/** 每次面试的指标明细（仅平台管理员可见） */
export function getInterviewMetrics(
  limit = 50,
  scope: 'me' | 'all' = 'all',
): Promise<InterviewMetricRow[]> {
  return client.get('/metrics/interviews', { params: { limit, scope } })
}
