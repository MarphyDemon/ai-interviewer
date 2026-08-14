import client from './client'

// ---------- 类型 ----------

export interface ProblemListItem {
  id: number
  title: string
  difficulty: string
  position: string
  tags: string[]
}

export interface ProblemExample {
  input: string
  output: string
  explanation?: string
}

export interface ProblemDetail extends ProblemListItem {
  description: string
  examples: ProblemExample[]
  timeLimitMs: number
  memoryLimitMb: number
}

export interface LanguageItem {
  id: string
  label: string
  template: string
}

export interface RunResult {
  stdout: string
  stderr: string
  exitCode: number
  signal: string | null
  durationMs: number
  compileError: string
}

export interface CaseResult {
  passed: boolean
  input: string
  expected: string
  actual: string
  stderr: string
}

export interface SubmitResult {
  submissionId: number
  status: string
  passCount: number
  totalCount: number
  durationMs: number
  stdout: string
  stderr: string
  compileError: string
  cases: CaseResult[]
}

export interface SubmissionRecord {
  id: number
  problemId: number
  language: string
  status: string
  passCount: number
  totalCount: number
  durationMs: number
  createdAt: string
}

// ---------- API ----------

export function getProblems(difficulty?: string): Promise<ProblemListItem[]> {
  const params = difficulty ? { difficulty } : undefined
  return client.get('/code/problems', { params })
}

export function getProblem(id: number): Promise<ProblemDetail> {
  return client.get(`/code/problems/${id}`)
}

export function getLanguages(): Promise<LanguageItem[]> {
  return client.get('/code/languages')
}

export function runCode(
  language: string,
  code: string,
  stdin = '',
): Promise<RunResult> {
  return client.post('/code/run', { language, code, stdin })
}

export function submitCode(
  problemId: number,
  language: string,
  code: string,
): Promise<SubmitResult> {
  return client.post('/code/submit', { problemId, language, code })
}

export function getHint(
  problemId: number,
  language: string,
  code: string,
  question: string,
): Promise<{ hint: string }> {
  return client.post('/code/hint', { problemId, language, code, question })
}

export function getSubmissions(problemId?: number): Promise<SubmissionRecord[]> {
  const params = problemId ? { problemId } : undefined
  return client.get('/code/submissions', { params })
}

// ---------- 流式 AI 对话 ----------

export interface CodeChatMessage {
  role: 'user' | 'assistant'
  content: string
}

/**
 * 流式算法陪练对话（SSE）。onDelta 收到增量文本，返回完整回复。
 */
export async function streamCodeChat(
  message: string,
  language: string,
  code: string,
  history: CodeChatMessage[],
  options: {
    difficulty?: string
    position?: string
    onDelta: (delta: string) => void
    signal?: AbortSignal
  },
): Promise<string> {
  const resp = await fetch('/api/code/chat/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${localStorage.getItem('user_token') || ''}`,
    },
    body: JSON.stringify({
      message,
      language,
      code,
      history,
      difficulty: options.difficulty || '中等',
      position: options.position || '算法',
    }),
    signal: options.signal,
  })
  if (!resp.ok || !resp.body) {
    const text = await resp.text().catch(() => '')
    throw new Error(text || `请求失败 (${resp.status})`)
  }

  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let full = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split('\n\n')
    buffer = parts.pop() || ''
    for (const part of parts) {
      const line = part.trim()
      if (!line.startsWith('data:')) continue
      const data = line.slice(5).trim()
      if (data === '[DONE]') return full
      try {
        const parsed = JSON.parse(data)
        if (parsed.error) throw new Error(parsed.error)
        if (parsed.delta) {
          full += parsed.delta
          options.onDelta(parsed.delta)
        }
      } catch {
        // 非 JSON 帧忽略
      }
    }
  }
  return full
}
