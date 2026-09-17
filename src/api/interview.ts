import client from './client'
import type {
  InterviewConfig,
  AIResponse,
  InterviewRecord,
  InterviewProblem,
  InterviewStage,
  BrainConfig,
  ChoiceIntent,
} from '@/types'

export function startInterview(
  config: InterviewConfig,
): Promise<{ interviewId: number; firstQuestion: AIResponse }> {
  return client.post('/interview/start', config)
}

export function submitAnswer(
  interviewId: number,
  answer: string,
): Promise<AIResponse> {
  return client.post(`/interview/${interviewId}/answer`, { answer })
}

/**
 * 签发面试专用 brain_config，让具身交互智能体 SDK 的 LLM 请求命中「面试官大脑」
 * 而不是聊天链路的「学习导师」。
 */
export function createInterviewAvatarSession(
  interviewId: number,
): Promise<BrainConfig> {
  return client.post(`/interview/${interviewId}/avatar-session`)
}

export function endInterview(interviewId: number): Promise<void> {
  return client.post(`/interview/${interviewId}/end`)
}

export function getInterviewHistory(): Promise<InterviewRecord[]> {
  return client.get('/interview/history')
}

export function getInterview(interviewId: number): Promise<InterviewRecord> {
  return client.get(`/interview/${interviewId}`)
}

export function deleteInterview(interviewId: number): Promise<void> {
  return client.delete(`/interview/${interviewId}`)
}

export function batchDeleteInterviews(ids: number[]): Promise<{ deleted: number }> {
  return client.post('/interview/batch-delete', { ids })
}

export interface InterviewJudgeResult {
  status: string
  passCount: number
  totalCount: number
  durationMs: number
  compileError: string
  cases: { passed: boolean; input: string; expected: string; actual: string }[]
}

export function submitInterviewCode(
  interviewId: number,
  data: { problemId: number; language: string; code: string },
): Promise<{ judgeResult: InterviewJudgeResult; nextQuestion: AIResponse }> {
  return client.post(`/interview/${interviewId}/submit-code`, data)
}

/** 交互控件（Picker）点选结果 */
export interface CommandResult {
  kind: 'question' | 'hint' | 'problem' | 'report'
  content?: string
  action?: string
  reasoning?: string
  problem?: InterviewProblem
  interviewId?: number
  stage?: InterviewStage
}

/**
 * 交互控件点选直达：确定性动作（换题 / 看提示 / 进入算法题 / 结束面试）
 * 由后端直接执行，不经过 LLM 解析。
 */
export function sendCommand(
  interviewId: number,
  intent: ChoiceIntent,
  label = '',
): Promise<CommandResult> {
  return client.post(`/interview/${interviewId}/command`, { intent, label })
}

/** 上报客户端实测指标（打断延迟） */
export function reportMetric(
  interviewId: number,
  valueMs: number,
  kind = 'interrupt',
): Promise<{ ok: boolean }> {
  return client.post(`/metrics/interview/${interviewId}`, { kind, valueMs })
}
