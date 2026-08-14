export interface UserInfo {
  id: number
  username: string
  preferredAvatarId: number | null
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
  asrConfig?: Record<string, unknown>
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
