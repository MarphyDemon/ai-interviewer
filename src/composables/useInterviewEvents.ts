import { ref } from 'vue'
import type {
  InterviewEmotionEvent,
  InterviewEvent,
  InterviewMetrics,
  InterviewWidget,
} from '@/types'
import { getApiBaseURL, getToken } from '@/api/client'

/**
 * 面试事件流（SSE 旁路）订阅 + Widget 栈管理。
 *
 * 为什么需要旁路：brain 代理的 SSE 正文字段会被具身交互智能体直接朗读，
 * 工具调用/Widget/情绪/时延这些结构化信息不能混进去，因此单独开一条通道。
 *
 * 状态放在模块级（单例），与 useAvatar 的写法保持一致。
 */

const widgets = ref<InterviewWidget[]>([])
const metrics = ref<InterviewMetrics | null>(null)
const activeTool = ref<string | null>(null)
const lastEmotion = ref<InterviewEmotionEvent | null>(null)
const connected = ref(false)

let source: EventSource | null = null
const ttlTimers = new Map<string, number>()

/** 同一 type+id 重复推送时只更新不叠加 */
function pushWidget(w: InterviewWidget) {
  if (!w || !w.type || !w.id) return

  const idx = widgets.value.findIndex((x) => x.type === w.type && x.id === w.id)
  if (idx >= 0) {
    widgets.value[idx] = w
    widgets.value = [...widgets.value]
  } else {
    widgets.value = [...widgets.value, w]
  }

  // TTL 到期自动收起
  const existing = ttlTimers.get(w.id)
  if (existing) {
    window.clearTimeout(existing)
    ttlTimers.delete(w.id)
  }
  if (typeof w.ttl === 'number' && w.ttl > 0) {
    const timer = window.setTimeout(() => removeWidget(w.id), w.ttl)
    ttlTimers.set(w.id, timer)
  }
}

function removeWidget(id: string) {
  const timer = ttlTimers.get(id)
  if (timer) {
    window.clearTimeout(timer)
    ttlTimers.delete(id)
  }
  widgets.value = widgets.value.filter((w) => w.id !== id)
}

function clearWidgets() {
  ttlTimers.forEach((t) => window.clearTimeout(t))
  ttlTimers.clear()
  widgets.value = []
}

function handleEvent(evt: InterviewEvent) {
  switch (evt.type) {
    case 'widget':
      pushWidget(evt.payload)
      break
    case 'tool_start':
      activeTool.value = evt.name
      break
    case 'tool_result':
      activeTool.value = null
      break
    case 'emotion':
      lastEmotion.value = { emotion: evt.emotion, ka: evt.ka, reason: evt.reason }
      break
    case 'metrics':
      metrics.value = { ttfaMs: evt.ttfaMs, toolMs: evt.toolMs, totalMs: evt.totalMs }
      break
  }
}

/** 建立事件流连接（重复调用会先断开旧的） */
async function connect(interviewId: number) {
  disconnect()

  // EventSource 无法自定义请求头，token 走查询参数
  const token = await getToken()
  if (!token) {
    console.warn('[InterviewEvents] 缺少 user_token，跳过事件流订阅')
    return
  }

  const url = `${getApiBaseURL()}/interview/${interviewId}/events?token=${encodeURIComponent(token)}`
  try {
    source = new EventSource(url)
  } catch (e) {
    console.warn('[InterviewEvents] EventSource 创建失败:', e)
    return
  }

  source.onopen = () => {
    connected.value = true
  }

  source.onmessage = (e) => {
    if (!e.data) return
    try {
      handleEvent(JSON.parse(e.data) as InterviewEvent)
    } catch (err) {
      console.warn('[InterviewEvents] 事件解析失败:', e.data, err)
    }
  }

  source.onerror = () => {
    // EventSource 会自动重连，这里只更新连接状态
    connected.value = false
  }
}

function disconnect() {
  if (source) {
    source.close()
    source = null
  }
  connected.value = false
  activeTool.value = null
}

export function useInterviewEvents() {
  return {
    widgets,
    metrics,
    activeTool,
    lastEmotion,
    connected,
    pushWidget,
    removeWidget,
    clearWidgets,
    connect,
    disconnect,
  }
}
