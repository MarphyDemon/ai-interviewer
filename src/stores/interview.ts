import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type {
  InterviewState,
  ChatMessage,
  InterviewConfig,
  AIResponse,
  InterviewProblem,
} from '@/types'
import * as interviewApi from '@/api/interview'

export const useInterviewStore = defineStore('interview', () => {
  const state = ref<InterviewState>('idle')
  const messages = ref<ChatMessage[]>([])
  const config = ref<InterviewConfig | null>(null)
  const interviewId = ref<number | null>(null)
  const currentQuestionIndex = ref(0)
  const currentFollowupLevel = ref(0)
  const errorMsg = ref('')
  const startTime = ref<number | null>(null)
  const currentProblem = ref<InterviewProblem | null>(null)
  const lastJudgeResult = ref<any>(null)

  // 响应式时钟：remainingTime 依赖它才能真正随时间变化
  // （直接读 Date.now() 不是响应式依赖，computed 永不重算，会导致倒计时静止）
  const nowTick = ref(Date.now())
  let ticker: ReturnType<typeof setInterval> | null = null

  function startTicker() {
    stopTicker()
    nowTick.value = Date.now()
    ticker = setInterval(() => {
      nowTick.value = Date.now()
    }, 1000)
  }

  function stopTicker() {
    if (ticker) {
      clearInterval(ticker)
      ticker = null
    }
  }

  const isRunning = computed(
    () =>
      state.value !== 'idle' &&
      state.value !== 'finished' &&
      state.value !== 'error',
  )

  const remainingTime = computed(() => {
    if (!startTime.value || !config.value) return 0
    const elapsed = Math.floor((nowTick.value - startTime.value) / 1000)
    const total = config.value.duration * 60
    return Math.max(0, total - elapsed)
  })

  function addMessage(role: ChatMessage['role'], content: string) {
    messages.value.push({
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      role,
      content,
      questionIndex: currentQuestionIndex.value,
      followupLevel: currentFollowupLevel.value,
      timestamp: Date.now(),
    })
  }

  function reset() {
    stopTicker()
    state.value = 'idle'
    messages.value = []
    config.value = null
    interviewId.value = null
    currentQuestionIndex.value = 0
    currentFollowupLevel.value = 0
    errorMsg.value = ''
    startTime.value = null
    currentProblem.value = null
    lastJudgeResult.value = null
  }

  async function start(cfg: InterviewConfig) {
    reset()
    const lang = (localStorage.getItem('lang') as 'en' | 'zh') || 'en'
    config.value = { ...cfg, lang }
    state.value = 'initializing'
    try {
      const res = await interviewApi.startInterview(config.value)
      interviewId.value = res.interviewId
      startTime.value = Date.now()
      startTicker()
      addMessage('interviewer', res.firstQuestion.content)
      handleAIResponse(res.firstQuestion)
    } catch (e: any) {
      state.value = 'error'
      errorMsg.value = e.message
    }
  }

  async function submitAnswer(answer: string) {
    if (!interviewId.value) return
    addMessage('user', answer)
    state.value = 'analyzing'
    currentProblem.value = null
    try {
      const res = await interviewApi.submitAnswer(interviewId.value, answer)
      addMessage('interviewer', res.content)
      handleAIResponse(res)
    } catch (e: any) {
      state.value = 'error'
      errorMsg.value = e.message
    }
  }

  async function submitCode(problemId: number, language: string, code: string) {
    if (!interviewId.value) return
    state.value = 'analyzing'
    currentProblem.value = null
    try {
      const res = await interviewApi.submitInterviewCode(interviewId.value, {
        problemId,
        language,
        code,
      })
      lastJudgeResult.value = res.judgeResult
      // 将判定结果摘要作为用户消息
      const summary = `[算法题提交] ${res.judgeResult.status} (${res.judgeResult.passCount}/${res.judgeResult.totalCount})`
      addMessage('user', summary)
      // 下一题
      addMessage('interviewer', res.nextQuestion.content)
      handleAIResponse(res.nextQuestion)
    } catch (e: any) {
      state.value = 'error'
      errorMsg.value = e.message
    }
  }

  function handleAIResponse(res: AIResponse) {
    switch (res.action) {
      case 'ask':
      case 'next_question':
        currentQuestionIndex.value++
        currentFollowupLevel.value = 0
        state.value = 'waiting_answer'
        currentProblem.value = null
        break
      case 'followup':
        currentFollowupLevel.value++
        state.value = 'waiting_answer'
        currentProblem.value = null
        break
      case 'algorithm':
        currentQuestionIndex.value++
        currentFollowupLevel.value = 0
        currentProblem.value = res.problem || null
        state.value = 'waiting_answer'
        break
      case 'end':
        stopTicker()
        state.value = 'generating_report'
        currentProblem.value = null
        break
    }
  }

  async function endInterview() {
    if (!interviewId.value) return
    stopTicker()
    state.value = 'generating_report'
    try {
      await interviewApi.endInterview(interviewId.value)
      state.value = 'finished'
    } catch (e: any) {
      state.value = 'error'
      errorMsg.value = e.message
    }
  }

  function setState(s: InterviewState) {
    state.value = s
  }

  return {
    state,
    messages,
    config,
    interviewId,
    currentQuestionIndex,
    currentFollowupLevel,
    errorMsg,
    startTime,
    currentProblem,
    lastJudgeResult,
    isRunning,
    remainingTime,
    addMessage,
    reset,
    start,
    submitAnswer,
    submitCode,
    endInterview,
    setState,
  }
})
