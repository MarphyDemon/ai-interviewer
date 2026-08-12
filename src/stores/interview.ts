import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type {
  InterviewState,
  ChatMessage,
  InterviewConfig,
  AIResponse,
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

  const isRunning = computed(
    () =>
      state.value !== 'idle' &&
      state.value !== 'finished' &&
      state.value !== 'error',
  )

  const remainingTime = computed(() => {
    if (!startTime.value || !config.value) return 0
    const elapsed = Math.floor((Date.now() - startTime.value) / 1000)
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
    state.value = 'idle'
    messages.value = []
    config.value = null
    interviewId.value = null
    currentQuestionIndex.value = 0
    currentFollowupLevel.value = 0
    errorMsg.value = ''
    startTime.value = null
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
      addMessage('interviewer', res.firstQuestion.content)
      state.value = 'waiting_answer'
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
    try {
      const res = await interviewApi.submitAnswer(interviewId.value, answer)
      addMessage('interviewer', res.content)
      handleAIResponse(res)
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
        break
      case 'followup':
        currentFollowupLevel.value++
        state.value = 'waiting_answer'
        break
      case 'end':
        state.value = 'generating_report'
        break
    }
  }

  async function endInterview() {
    if (!interviewId.value) return
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
    isRunning,
    remainingTime,
    addMessage,
    reset,
    start,
    submitAnswer,
    endInterview,
    setState,
  }
})
