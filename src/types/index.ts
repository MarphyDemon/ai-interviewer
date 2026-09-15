export interface NotificationSettings {
  collaboration: boolean
  review: boolean
  system: boolean
}

export interface UserInfo {
  id: number
  username: string
  role: 'user' | 'admin'
  preferredAvatarConfigId: number | null
  preferredPosition: string
  language: 'zh' | 'en'
  theme: 'light' | 'dark'
  notificationSettings: NotificationSettings
}

export interface UserQuota {
  plan: 'free' | 'standard' | 'enterprise'
  interviewLimit: number
  interviewUsed: number
  knowledgeLimit: number
  knowledgeUsed: number
  aiCallsLimit: number
  aiCallsUsed: number
}

export interface KnowledgeVersionInfo {
  id: number
  versionNumber: number
  title: string
  changeNote: string
  createdBy: number | null
  createdAt: string
}

export interface KnowledgeVersionDetail {
  id: number
  versionNumber: number
  content: string
  title: string
  position: string
  difficulty: string
  tags: string[]
  changeNote: string
  createdBy: number | null
  createdAt: string
}

export interface CollaboratorInfo {
  id: number
  userId: number
  username: string
  permission: 'read' | 'edit' | 'admin'
  createdAt: string
}

export interface NotificationItem {
  id: number
  type: 'collaboration' | 'review' | 'system'
  title: string
  content: string
  isRead: boolean
  createdAt: string
}

export type Difficulty = 'junior' | 'mid' | 'senior'

export type InterviewerStyle = 'strict' | 'friendly' | 'pressure'

export interface InterviewConfig {
  position: string
  difficulty: Difficulty
  duration: number
  style?: InterviewerStyle
  resumeId?: number
  jdId?: number
  lang?: 'en' | 'zh'
}

export type InterviewState =
  | 'idle'
  | 'initializing'
  | 'asking'
  | 'waiting_answer'
  | 'analyzing'
  | 'followup_asking'
  | 'generating_report'
  | 'finished'
  | 'error'

export type MessageRole = 'interviewer' | 'user'

export interface ChatMessage {
  id: string
  role: MessageRole
  content: string
  questionIndex?: number
  followupLevel?: number
  timestamp: number
}

export type AIAction = 'ask' | 'followup' | 'next_question' | 'algorithm' | 'end'

export interface InterviewProblem {
  id: number
  title: string
  description: string
  difficulty: string
  tags: string[]
  examples: { input: string; output: string; explanation?: string }[]
  timeLimitMs: number
  memoryLimitMb: number
}

export interface AIResponse {
  action: AIAction
  content: string
  reasoning?: string
  problem?: InterviewProblem
}

export interface AvatarConfig {
  appId: string
  appSecret: string
  gatewayServer: string
  avatarImage?: string
  asrConfig?: Record<string, unknown>
}

export interface BrainConfig {
  provider: string
  model: string
  api_key: string
  base_url: string
  extra_body?: Record<string, unknown>
  conversation?: {
    id: number
    title: string
    created_at: string | null
  }
}

export interface AgentLLMResponse {
  event: 'chunk' | 'done'
  text?: string
  isFirst?: boolean
  usage?: {
    promptTokens: number
    completionTokens: number
    totalTokens: number
    cachedTokens: number
  }
}

export interface KnowledgeDoc {
  id: number
  filename: string
  title: string
  position: string
  difficulty: string
  tags: string[]
  status: 'processing' | 'ready' | 'failed'
  createdAt: string
}

export interface ResumeInfo {
  id: number
  filename: string
  parsedText: string
  analysisResult: {
    structureScore: number
    positionMatch: number
    highlights: string[]
    weaknesses: string[]
  }
  createdAt: string
}

export interface JobDescription {
  id: number
  title: string
  content: string
  position: string
  createdAt: string
  updatedAt: string
}

export interface InterviewRecord {
  id: number
  position: string
  difficulty: string
  duration: number
  style: string
  status: '进行中' | '已结束'
  startedAt: string
  endedAt: string | null
}

export interface DimensionScore {
  label: string
  score: number
}

export interface QuestionReview {
  question: string
  answer: string
  review: string
  referenceAnswer: string
  score: number
}

export interface MatchBreakdownItem {
  requirement: string
  status: 'met' | 'partial' | 'gap'
  evidence: string
}

export interface ReportData {
  id: number
  interviewId: number
  totalScore: number
  dimensionScores: DimensionScore[]
  summary: string
  perQuestionReviews: QuestionReview[]
  resumeReview?: {
    structureScore: number
    positionMatch: number
    highlights: string[]
    weaknesses: string[]
  }
  jobFit?: string
  matchScore?: number | null
  matchBreakdown?: MatchBreakdownItem[]
  createdAt: string
}

export interface LLMConfig {
  id: number
  name: string
  baseUrl: string
  apiKeyMasked: string
  model: string
  isActive: boolean
}

export interface ASRResult {
  text: string
  isFinal: boolean
}

// ===== 面试事件流（SSE 旁路）与 Widget =====

/** Widget 类型：与后端 interview_tools.execute_tool 返回的 widget.type 一一对应 */
export type InterviewWidgetType =
  | 'resume_highlight'
  | 'match_score'
  | 'question_card'
  | 'judge_result'
  | 'interview_report'
  | 'score'

export interface InterviewWidget {
  type: InterviewWidgetType
  /** 同 type 下用于去重/更新的标识 */
  id: string
  data: Record<string, any>
  /** 毫秒；省略表示常驻，需手动关闭 */
  ttl?: number
}

export interface MatchBreakdownItemLite {
  requirement: string
  status: 'met' | 'partial' | 'gap'
  evidence: string
}

export interface JudgeCaseLite {
  passed: boolean
  input: string
  expected: string
  actual: string
}

export interface InterviewMetrics {
  /** 首字延迟：用户说完 → 具身交互智能体开口（毫秒） */
  ttfaMs: number | null
  /** 本轮流式生成中工具调用的累计耗时 */
  toolMs: number
  /** 本轮端到端耗时 */
  totalMs: number
}

export interface InterviewToolEvent {
  name: string
  ok?: boolean
  ms?: number
  round?: number
}

export interface InterviewEmotionEvent {
  emotion: string
  ka: string
  reason: string
}

/** 面试事件流推送的事件联合类型 */
export type InterviewEvent =
  | { type: 'widget'; payload: InterviewWidget }
  | { type: 'tool_start'; name: string; round: number }
  | ({ type: 'tool_result' } & InterviewToolEvent)
  | ({ type: 'emotion' } & InterviewEmotionEvent)
  | ({ type: 'metrics' } & InterviewMetrics)

/** 具身交互智能体 SDK 下发的原始 Widget 事件（proxyWidget 回调入参） */
export interface RawWidgetEvent {
  type: string
  data?: Record<string, any>
  text?: string
  speech_id?: number
  client_speak_id?: string | number
}

export interface ChatConversation {
  id: number
  title: string
  createdAt: string
  updatedAt: string
}

export interface ChatMessageItem {
  id: number
  role: 'user' | 'assistant'
  content: string
  createdAt: string
}

export interface InterviewTemplate {
  id: number
  name: string
  position: string
  difficulty: Difficulty
  duration: number
  style: InterviewerStyle
  description: string
  builtIn: boolean
  createdAt: string
}

export interface ComparisonResult {
  question: string
  answers: {
    userAnswer: string
    referenceAnswer: string
    score: number
    highlights: string[]
    improvements: string[]
  }
}
