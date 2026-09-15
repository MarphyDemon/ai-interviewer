import client from './client'
import type {
  InterviewConfig,
  AIResponse,
  InterviewRecord,
  BrainConfig,
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
