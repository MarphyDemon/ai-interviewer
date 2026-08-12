export type Difficulty = 'junior' | 'mid' | 'senior'

export type InterviewerStyle = 'strict' | 'friendly' | 'pressure'

export interface InterviewConfig {
  position: string
  difficulty: Difficulty
  duration: number
  style?: InterviewerStyle
  resumeId?: number
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

export type AIAction = 'ask' | 'followup' | 'next_question' | 'end'

export interface AIResponse {
  action: AIAction
  content: string
  reasoning?: string
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
