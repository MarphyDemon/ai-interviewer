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
