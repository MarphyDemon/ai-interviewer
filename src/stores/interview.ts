import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type {
  InterviewState,
  ChatMessage,
  InterviewConfig,
  AIResponse,
  InterviewProblem,
  InterviewStage,
  InterviewChoice,
} from '@/types'
import * as interviewApi from '@/api/interview'
import type { InviteStartResult } from '@/api/invite'
import { useInterviewEvents } from '@/composables/useInterviewEvents'

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
  /** 面试流程状态机阶段（后端 stage 事件 / 接口返回值同步） */
  const stage = ref<InterviewStage | null>(null)
  /** 当前待点选的交互控件选项（picker widget） */
  const choices = ref<InterviewChoice[]>([])
  /** 客户端侧实测指标（如打断延迟），供 /metrics 页面查看 */
  const lastInterruptMs = ref<number | null>(null)

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
    stage.value = null
    choices.value = []
    lastInterruptMs.value = null
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

  /**
   * 候选人凭邀请链接进入后接管面试状态。
   * token 由后端签发（role="candidate" 的无密码用户），由调用方写入 user store，
   * 之后面试页与个人练习走的是完全相同的接口与状态机。
   */
  function startFromInvite(payload: InviteStartResult) {
    reset()
    const lang = (localStorage.getItem('lang') as 'en' | 'zh') || 'en'
    config.value = {
      position: payload.config.position,
      difficulty: payload.config.difficulty as InterviewConfig['difficulty'],
      duration: payload.config.duration,
      style: payload.config.style as InterviewConfig['style'],
      lang,
    }
    interviewId.value = payload.interviewId
    startTime.value = Date.now()
    startTicker()
    state.value = 'initializing'
    addMessage('interviewer', payload.firstQuestion.content)
    handleAIResponse(payload.firstQuestion as AIResponse)
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

  /** 同步状态机阶段（接口返回值与 SSE stage 事件都会调到这里） */
  function applyStage(next?: InterviewStage | null) {
    if (!next) return
    stage.value = next
    useInterviewEvents().setStage(next)
  }

  function handleAIResponse(res: AIResponse) {
    applyStage(res.stage)
    choices.value = res.choices || []
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
      case 'choices':
        // 面试官给出可点选项，等待候选人点选（点选后走 /command 直达，不经 LLM）
        currentProblem.value = null
        state.value = 'waiting_answer'
        break
      case 'end':
        stopTicker()
        state.value = 'generating_report'
        currentProblem.value = null
        break
      default:
        // 未知 action（如后端新增类型）不应让页面卡在"分析中"
        state.value = 'waiting_answer'
        break
    }
  }

  /** 交互控件点选直达：不经过 LLM 解析 */
  async function selectChoice(choice: InterviewChoice) {
    if (!interviewId.value || !choice) return
    state.value = 'analyzing'
    choices.value = []
    try {
      const res = await interviewApi.sendCommand(
        interviewId.value,
        choice.intent,
        choice.label,
      )
      applyStage(res.stage)
      if (res.content) addMessage('interviewer', res.content)
      if (res.problem) currentProblem.value = res.problem
      if (res.kind === 'report') {
        stopTicker()
        state.value = 'generating_report'
      } else {
        state.value = 'waiting_answer'
      }
    } catch (e: any) {
      state.value = 'error'
      errorMsg.value = e.message
    }
  }

  /** 上报客户端侧实测指标（打断延迟） */
  async function reportInterrupt(ms: number) {
    lastInterruptMs.value = ms
    if (!interviewId.value) return
    try {
      await interviewApi.reportMetric(interviewId.value, ms)
    } catch (e) {
      console.warn('[Interview] 打断延迟上报失败:', e)
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
    stage,
    choices,
    lastInterruptMs,
    isRunning,
    remainingTime,
    addMessage,
    reset,
    start,
    startFromInvite,
    submitAnswer,
    submitCode,
    applyStage,
    selectChoice,
    reportInterrupt,
    endInterview,
    setState,
  }
})
