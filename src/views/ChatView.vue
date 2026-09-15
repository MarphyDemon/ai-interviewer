<script setup lang="ts">
import { onMounted, onUnmounted, ref, nextTick, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useChatStore } from '@/stores/chat'
import { useAvatar } from '@/composables/useAvatar'
import { useDevice } from '@/composables/useDevice'
import { renderMarkdown } from '@/utils/markdown'
import type { AgentLLMResponse } from '@/types'

const { t } = useI18n()
const store = useChatStore()
const { initAvatar, getProvider, destroyAvatar, lastBrainConfig } = useAvatar()
const { isMobile, windowWidth } = useDevice()

const isNarrow = computed(() => windowWidth.value < 1024)

const input = ref('')
const messagesEl = ref<HTMLElement | null>(null)
const showAvatar = ref(false)
const editingId = ref<number | null>(null)
const editingTitle = ref('')

// 具身交互智能体状态
const avatarLoading = ref(false)
const avatarFailed = ref(false)
const autoSpeak = ref(true)
const listening = ref(false)
const speaking = ref(false)
const speakBuffer = ref('')
const streamAborted = ref(false)
const avatarConversationId = ref<number | null>(null)
const avatarPendingAssistantId = ref<number | null>(null)
const avatarResponseBuffer = ref('')

// 全屏状态
const avatarStageEl = ref<HTMLElement | null>(null)
const isFullscreen = ref(false)
const fullscreenPartialText = ref('')
const sdkSubtitleText = ref('')
const sdkSubtitleVisible = ref(false)

// 持续对话状态 (Plan C)
const fullscreenListening = ref(false)
const pendingFullscreenMessage = ref<string | null>(null)
let fullscreenASRRunning = false
let fullscreenStartPromise: Promise<void> | null = null
let fullscreenStopRequested = false
let isRestartingFromSend = false

// ASR 文字自动消失计时器
let asrAutoClearTimer: ReturnType<typeof setTimeout> | null = null
function scheduleAsrAutoClear(delay = 4000) {
  if (asrAutoClearTimer) clearTimeout(asrAutoClearTimer)
  asrAutoClearTimer = setTimeout(() => {
    fullscreenPartialText.value = ''
    asrAutoClearTimer = null
  }, delay)
}
function cancelAsrAutoClear() {
  if (asrAutoClearTimer) {
    clearTimeout(asrAutoClearTimer)
    asrAutoClearTimer = null
  }
}

const hasConversation = computed(() => store.currentId !== null)

function handleFullscreenKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && isFullscreen.value) {
    exitFullscreen()
  }
}

onMounted(async () => {
  await store.fetchConversations()
  window.addEventListener('keydown', handleFullscreenKeydown)
})

onUnmounted(() => {
  stopSpeaking()
  stopListening()
  fullscreenASRRunning = false
  fullscreenStartPromise = null
  fullscreenStopRequested = false
  isRestartingFromSend = false
  fullscreenListening.value = false
  pendingFullscreenMessage.value = null
  disconnectAvatarResize()
  destroyAvatar()
  window.removeEventListener('keydown', handleFullscreenKeydown)
})

// 流式输出时持续滚动到底部
watch(
  () => store.currentMessages.map((m) => m.content).join(''),
  () => scrollToBottom(),
)

// 全屏状态变化时滚动到底部，确保退出全屏后消息可见
watch(isFullscreen, (fullscreen) => {
  if (!fullscreen) {
    nextTick(() => scrollToBottom())
  }
})

// 全屏自动打断：当流式生成被打断后，自动发送暂存的消息 或 重启 ASR
watch(() => store.streaming, async (streaming) => {
  if (streaming) return
  if (!isFullscreen.value) return

  if (pendingFullscreenMessage.value) {
    // 始终优先处理暂存的打断消息（即使在 send 流程中被再次打断）
    const msg = pendingFullscreenMessage.value
    pendingFullscreenMessage.value = null
    await sendFullscreenMessage(msg)
  } else if (!isRestartingFromSend) {
    // 正常停止/异常中断后，重启 ASR（排除 send 流程自身触发的 streaming 变化）
    startFullscreenASR()
  }
})

// 切换会话时销毁具身交互智能体（避免消息写错会话）
watch(() => store.currentId, async (newId, oldId) => {
  if (showAvatar.value && newId !== oldId && oldId !== null) {
    stopSpeaking()
    stopListening()
    await destroyAvatar()
    showAvatar.value = false
    avatarFailed.value = false
    avatarConversationId.value = null
  }
})

// 窗口尺寸变化时无需重新初始化，容器始终存在于 DOM 中
// 使用 ResizeObserver 监听容器尺寸/位置变化，通知底层 SDK 重新适配画布
let resizeObserver: ResizeObserver | null = null

async function observeAvatarResize() {
  await nextTick()
  const stage = avatarStageEl.value
  if (!stage) return
  resizeObserver?.disconnect()
  resizeObserver = new ResizeObserver(() => {
    const provider = getProvider()
    if (provider?.resize) provider.resize()
  })
  resizeObserver.observe(stage)
}

function disconnectAvatarResize() {
  resizeObserver?.disconnect()
  resizeObserver = null
}

async function scrollToBottom() {
  await nextTick()
  if (messagesEl.value) {
    messagesEl.value.scrollTop = messagesEl.value.scrollHeight
  }
}

/** 把 Markdown 清理成可朗读的纯文本（去掉代码块/标记符号） */
function cleanForSpeech(text: string): string {
  return text
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/`([^`]*)`/g, '$1')
    .replace(/^#{1,6}\s*/gm, '')
    .replace(/\*\*([^*]*)\*\*/g, '$1')
    .replace(/\*([^*]*)\*/g, '$1')
    .replace(/^>\s*/gm, '')
    .replace(/^[-*+]\s+/gm, '')
    .replace(/^\d+\.\s+/gm, '')
    .replace(/[#*`>_~]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
}

/** 流式喂入增量文本，按句子边界切分后立即送播（边生成边讲） */
function feedSpeak(delta: string) {
  if (!autoSpeak.value || streamAborted.value) return
  const provider = getProvider()
  if (!provider || !provider.isReady() || !provider.speakChunk) return
  speakBuffer.value += delta
  // 循环取出所有已完成句子
  let m = speakBuffer.value.match(/^(.*?[。！？；.!?;\n])(.*)$/s)
  while (m) {
    const sentence = cleanForSpeech(m[1])
    if (sentence) provider.speakChunk!(sentence)
    speakBuffer.value = m[2]
    m = speakBuffer.value.match(/^(.*?[。！？；.!?;\n])(.*)$/s)
  }
}

/** 流结束后把剩余缓冲作为最后一帧（is_end=true）发送 */
function endSpeak() {
  if (!autoSpeak.value || streamAborted.value) return
  const provider = getProvider()
  const remaining = speakBuffer.value
  speakBuffer.value = ''
  if (!provider || !provider.isReady()) return
  const text = remaining.trim() ? cleanForSpeech(remaining) : ''
  provider.endSpeakStream?.(text)
}

async function handleSend() {
  const msg = input.value.trim()
  if (!msg || store.streaming) return
  input.value = ''
  if (isFullscreen.value) {
    await sendFullscreenMessage(msg)
    return
  }
  streamAborted.value = false
  if (autoSpeak.value) {
    stopSpeaking()
    getProvider()?.startSpeakStream?.()
  }
  await store.sendMessage(msg, (delta) => feedSpeak(delta))
  if (autoSpeak.value && !streamAborted.value) endSpeak()
  streamAborted.value = false
  scrollToBottom()
}

/** 中断当前回答生成（同时停止具身交互智能体播报），保留已生成内容 */
function handleStop() {
  streamAborted.value = true
  speakBuffer.value = ''
  store.stopGeneration()
  stopSpeaking()
}

/** 切换具身交互智能体显示/隐藏 */
async function toggleAvatar() {
  if (showAvatar.value) {
    stopSpeaking()
    stopListening()
    disconnectAvatarResize()
    await destroyAvatar()
    showAvatar.value = false
    avatarFailed.value = false
    avatarConversationId.value = null
    return
  }

  // 确保有选中的会话（无则自动创建）
  if (!store.currentId) {
    await store.newConversation()
  }
  const convId = store.currentId!

  showAvatar.value = true
  avatarLoading.value = true
  avatarFailed.value = false
  avatarConversationId.value = convId
  await nextTick()

  try {
    // 传递 conversationId，让后端绑定到当前会话
    const provider = await initAvatar('chat-avatar-container', convId)
    observeAvatarResize()

    // 如果后端返回了新会话（conversation_id 不同），则选中它
    if (lastBrainConfig.value?.conversation) {
      const backendConvId = lastBrainConfig.value.conversation.id
      if (backendConvId !== convId) {
        avatarConversationId.value = backendConvId
        // 选中新会话并加载消息
        await store.selectConversation(backendConvId)
      }
    }

    // 注册字幕回调
    if (provider.setOnSubtitle) {
      provider.setOnSubtitle((text, on) => {
        if (on && text) {
          sdkSubtitleText.value = text
          sdkSubtitleVisible.value = true
        } else {
          sdkSubtitleVisible.value = false
        }
      })
    }

    // 注册 LLM 响应回调（SDK → 前端实时展示）
    if (provider.setOnLLMResponse) {
      provider.setOnLLMResponse(handleAvatarLLMResponse)
    }
  } catch (e) {
    console.warn('[Chat Avatar] init failed:', e)
    avatarFailed.value = true
  } finally {
    avatarLoading.value = false
  }
}

/** 处理具身交互智能体 LLM 响应（SDK 回调 → 前端实时展示） */
function handleAvatarLLMResponse(response: AgentLLMResponse) {
  if (response.event === 'chunk' && response.text) {
    // 流式追加：创建或追加到 assistant 消息
    let assistantMsgId = avatarPendingAssistantId.value
    if (assistantMsgId) {
      const msg = store.currentMessages.find(m => m.id === assistantMsgId)
      if (msg) {
        msg.content += response.text
        avatarResponseBuffer.value += response.text
        scrollToBottom()
        return
      }
    }
    // 新建 assistant 消息
    const newId = Date.now() + Math.floor(Math.random() * 1000)
    avatarPendingAssistantId.value = newId
    avatarResponseBuffer.value = response.text
    store.currentMessages.push({
      id: newId,
      role: 'assistant',
      content: response.text,
      createdAt: new Date().toISOString(),
    })
    scrollToBottom()
  } else if (response.event === 'done') {
    // LLM 回复完成 → 从 DB 同步最终结果
    avatarPendingAssistantId.value = null
    avatarResponseBuffer.value = ''
    if (avatarConversationId.value) {
      store.selectConversation(avatarConversationId.value)
    }
  }
}

function speakText(text: string) {
  const provider = getProvider()
  if (!provider || !provider.isReady()) return
  speaking.value = true
  provider.speak(text).finally(() => {
    speaking.value = false
  })
}

function stopSpeaking() {
  const provider = getProvider()
  if (!provider) return
  provider.stopSpeakStream?.()
  provider.interrupt?.()
  speakBuffer.value = ''
  speaking.value = false
}

/** 窄屏/侧栏模式下的手动麦克风 (push-to-talk) */
function toggleMic() {
  if (listening.value) {
    stopListening()
    return
  }
  const provider = getProvider()
  if (!provider || !provider.isReady()) return
  listening.value = true
  provider.startASR((result) => {
    if (result.isFinal && result.text) {
      if (showAvatar.value && avatarConversationId.value) {
        // 具身交互智能体激活时：用户语音消息直接显示（SDK brain_config 会处理 LLM）
        store.currentMessages.push({
          id: Date.now(),
          role: 'user',
          content: result.text,
          createdAt: new Date().toISOString(),
        })
        scrollToBottom()
      } else {
        input.value = (input.value + ' ' + result.text).trim()
      }
    }
  }).catch(() => {
    listening.value = false
  })
}

function stopListening() {
  if (!listening.value) return
  const provider = getProvider()
  provider?.stopASR?.()
  listening.value = false
}

/** 启动全屏持续 ASR 监听 (Plan C) - 带竞态保护 */
async function startFullscreenASR() {
  if (fullscreenASRRunning) return
  if (fullscreenStartPromise) {
    // 已有 start 进行中，等它完成
    await fullscreenStartPromise
    return
  }
  const provider = getProvider()
  if (!provider || !provider.isReady()) return

  fullscreenStartPromise = (async () => {
    try {
      fullscreenStopRequested = false
      await provider.startASR((result) => {
        if (fullscreenStopRequested) return
        if (result.isFinal && result.text) {
          const msg = result.text.trim()
          fullscreenPartialText.value = msg
          if (!msg) return
          if (showAvatar.value && avatarConversationId.value) {
            // 具身交互智能体激活时：用户语音消息直接显示（SDK brain_config 处理 LLM）
            store.currentMessages.push({
              id: Date.now(),
              role: 'user',
              content: msg,
              createdAt: new Date().toISOString(),
            })
            scrollToBottom()
          } else if (store.streaming) {
            // 自动打断 (Plan A)
            pendingFullscreenMessage.value = msg
            streamAborted.value = true
            speakBuffer.value = ''
            store.stopGeneration()
            stopSpeaking()
            // 打断后临时停 ASR，等待重启
            const p = getProvider()
            p?.stopASR?.()
            fullscreenASRRunning = false
            fullscreenListening.value = false
            listening.value = false
          } else {
            sendFullscreenMessage(msg)
          }
        } else {
          fullscreenPartialText.value = result.text
          scheduleAsrAutoClear()
        }
      })
      if (!fullscreenStopRequested) {
        fullscreenASRRunning = true
        fullscreenListening.value = true
        listening.value = true
      }
    } catch {
      fullscreenASRRunning = false
      fullscreenListening.value = false
      listening.value = false
    } finally {
      fullscreenStartPromise = null
    }
  })()
  await fullscreenStartPromise
}

/** 停止全屏持续 ASR 监听 - 带竞态保护 */
async function stopFullscreenASR() {
  fullscreenStopRequested = true
  if (fullscreenStartPromise) {
    await fullscreenStartPromise
    fullscreenStartPromise = null
  }
  if (fullscreenASRRunning) {
    const provider = getProvider()
    await provider?.stopASR?.()
    fullscreenASRRunning = false
  }
  fullscreenListening.value = false
  listening.value = false
}

/** 切换全屏 ASR 监听状态 - Plan C 下 mic 按钮为静音开关 */
function toggleFullscreenListening() {
  if (fullscreenASRRunning || fullscreenStartPromise) {
    stopFullscreenASR()
  } else {
    startFullscreenASR()
  }
}

/** 进入具身交互智能体全屏 - 具身交互智能体展示，ASR 等待用户点击麦克风启动 */
function enterFullscreen() {
  isFullscreen.value = true
  fullscreenPartialText.value = ''
  cancelAsrAutoClear()
}

/** 退出具身交互智能体全屏 */
async function exitFullscreen() {
  isFullscreen.value = false
  cancelAsrAutoClear()
  pendingFullscreenMessage.value = null
  await stopFullscreenASR()
  if (store.streaming) {
    streamAborted.value = true
    store.stopGeneration()
    stopSpeaking()
  }
  fullscreenPartialText.value = ''
  nextTick(() => scrollToBottom())
}

/** 全屏/窄屏 下直接发送消息 */
async function sendFullscreenMessage(msg: string) {
  streamAborted.value = false
  // 发送前停止 ASR，避免回声（带竞态保护）
  if (fullscreenASRRunning || fullscreenStartPromise) {
    await stopFullscreenASR()
  }
  if (autoSpeak.value) {
    stopSpeaking()
    getProvider()?.startSpeakStream?.()
  }
  // 标记正在从发送流程中重启，避免 watcher 重复触发
  isRestartingFromSend = true
  try {
    await store.sendMessage(msg, (delta) => feedSpeak(delta))
    if (autoSpeak.value && !streamAborted.value) endSpeak()
  } finally {
    isRestartingFromSend = false
  }
  streamAborted.value = false
  scrollToBottom()
  // 回复完成后自动重启 ASR 持续监听
  if (isFullscreen.value) {
    startFullscreenASR()
  }
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}

async function handleNew() {
  await store.newConversation()
}

function startRename(id: number, title: string) {
  editingId.value = id
  editingTitle.value = title
}

async function commitRename(id: number) {
  const title = editingTitle.value.trim()
  editingId.value = null
  if (title) {
    await store.rename(id, title)
  }
}

async function handleDelete(id: number) {
  if (!confirm(t('history.confirmDelete'))) return
  await store.remove(id)
}
</script>

<template>
  <div
    class="relative flex"
    :class="[
      isMobile ? 'h-[calc(100vh-60px)]' : 'h-[calc(100vh-4rem)]',
      { 'overflow-hidden': !isFullscreen, 'overflow-visible': isFullscreen },
    ]"
  >
    <!-- 左：会话列表 -->
    <aside class="hidden w-64 shrink-0 flex-col border-r border-primary-100/60 bg-white/60 backdrop-blur md:flex">
      <div class="p-3">
        <button class="btn-primary w-full !py-2 text-sm" :disabled="store.newConversationLoading" @click="handleNew">
          <svg v-if="!store.newConversationLoading" viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4" /></svg>
          <div v-else class="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white"></div>
          {{ store.newConversationLoading ? t('common.loading') : t('chat.newConversation') }}
        </button>
      </div>
      <div class="flex-1 overflow-y-auto px-2 pb-3">
        <div v-if="store.conversationsLoading" class="space-y-2 px-1 py-4">
          <div v-for="i in 5" :key="i" class="h-8 animate-pulse rounded-lg bg-gray-100"></div>
        </div>
        <template v-else>
          <button
            v-for="conv in store.conversations"
            :key="conv.id"
            @click="store.selectConversation(conv.id)"
            :class="[
              'group mb-1 flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm transition',
              store.currentId === conv.id ? 'bg-primary-50 text-primary-700' : 'text-gray-600 hover:bg-primary-50/50',
              store.selectLoading && store.currentId === conv.id ? 'opacity-70' : '',
            ]"
          >
            <svg viewBox="0 0 24 24" class="h-4 w-4 shrink-0 text-primary-400" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M8 10h.01M12 10h.01M16 10h.01M21 12a8 8 0 01-8 8H7l-4 3v-6a8 8 0 018-11h2a8 8 0 018 6z" /></svg>
            <span v-if="editingId === conv.id" class="flex-1">
              <input
                v-model="editingTitle"
                @keydown.enter="commitRename(conv.id)"
                @blur="commitRename(conv.id)"
                @click.stop
                class="w-full rounded border border-primary-300 px-1 py-0.5 text-xs focus:outline-none"
                autofocus
              />
            </span>
            <span v-else class="flex-1 truncate">{{ conv.title }}</span>
            <span v-if="store.selectLoading && store.currentId === conv.id" class="h-3 w-3 animate-spin rounded-full border-2 border-primary-200 border-t-primary-600"></span>
            <span v-else-if="store.removeLoading === conv.id" class="h-3 w-3 animate-spin rounded-full border-2 border-red-200 border-t-red-500"></span>
            <span v-else-if="editingId !== conv.id" class="hidden shrink-0 gap-1 group-hover:flex">
              <button @click.stop="startRename(conv.id, conv.title)" class="text-gray-400 hover:text-primary-600" :title="t('chat.rename')">
                <svg viewBox="0 0 24 24" class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" /></svg>
              </button>
              <button @click.stop="handleDelete(conv.id)" :disabled="store.removeLoading !== null" class="text-gray-400 hover:text-red-600 disabled:opacity-50" :title="t('chat.delete')">
                <svg viewBox="0 0 24 24" class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
              </button>
            </span>
          </button>
          <p v-if="store.conversations.length === 0" class="px-3 py-6 text-center text-xs text-gray-400">{{ t('chat.empty') }}</p>
        </template>
      </div>
    </aside>

    <!-- 中：对话区 -->
    <main class="flex min-w-0 flex-1 flex-col">
      <!-- 顶栏 -->
      <div class="flex h-14 items-center justify-between border-b border-primary-100/60 px-4">
        <button class="btn-ghost !px-3 !py-1.5 text-xs md:hidden" @click="handleNew">{{ t('chat.newConversation') }}</button>
        <p class="truncate text-sm font-medium text-gray-600">
          {{ store.conversations.find((c) => c.id === store.currentId)?.title || t('chat.empty') }}
        </p>
        <button
          @click="toggleAvatar"
          :class="['rounded-lg px-3 py-1.5 text-xs font-medium transition', showAvatar ? 'bg-primary-50 text-primary-700' : 'text-gray-500 hover:bg-primary-50/60']"
        >
          {{ showAvatar ? t('chat.hideAvatar') : t('chat.showAvatar') }}
        </button>
      </div>

      <!-- 消息列表 -->
      <div ref="messagesEl" class="flex-1 overflow-y-auto px-4 py-6">
        <div v-if="!hasConversation" class="flex h-full flex-col items-center justify-center text-center">
          <span class="mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-brand text-white shadow-glow">
            <svg viewBox="0 0 24 24" class="h-8 w-8" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M8 10h.01M12 10h.01M16 10h.01M21 12a8 8 0 01-8 8H7l-4 3v-6a8 8 0 018-11h2a8 8 0 018 6z" /></svg>
          </span>
          <p class="text-lg font-semibold text-gray-700">{{ t('chat.empty') }}</p>
          <p class="mt-2 max-w-sm text-sm text-gray-400">{{ t('chat.emptyHint') }}</p>
          <button class="btn-primary mt-6" :disabled="store.newConversationLoading" @click="handleNew">
            {{ store.newConversationLoading ? t('common.loading') : t('chat.newConversation') }}
          </button>
        </div>

        <div v-else-if="store.selectLoading" class="mx-auto max-w-3xl space-y-4 py-8">
          <div v-for="i in 3" :key="i" :class="['flex', i % 2 === 0 ? 'justify-start' : 'justify-end']">
            <div class="h-10 w-3/4 animate-pulse rounded-2xl bg-gray-100"></div>
          </div>
          <div class="text-center">
            <div class="inline-flex items-center gap-2 text-sm text-gray-400">
              <span class="h-4 w-4 animate-spin rounded-full border-2 border-primary-200 border-t-primary-600"></span>
              {{ t('common.loading') }}
            </div>
          </div>
        </div>

        <div v-else class="mx-auto max-w-3xl space-y-5">
          <div
            v-for="msg in store.currentMessages"
            :key="msg.id"
            :class="['flex', msg.role === 'user' ? 'justify-end' : 'justify-start']"
          >
            <div :class="['flex max-w-[80%] gap-2', msg.role === 'user' ? 'flex-row-reverse' : 'flex-row']">
              <span
                :class="[
                  'flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-white',
                  msg.role === 'user' ? 'bg-gray-400' : 'bg-gradient-brand',
                ]"
              >
                <svg v-if="msg.role === 'user'" viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" /></svg>
                <svg v-else viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" /></svg>
              </span>
              <div :class="['flex flex-col', msg.role === 'user' ? 'items-end' : 'items-start']">
                <div
                  :class="[
                    'rounded-2xl px-4 py-2.5 text-sm leading-relaxed shadow-soft break-words',
                    msg.role === 'user'
                      ? 'rounded-tr-sm bg-gradient-brand text-white'
                      : 'rounded-tl-sm border border-primary-100/60 bg-white text-gray-700',
                  ]"
                >
                  <template v-if="msg.content">
                    <span v-if="msg.role === 'user'">{{ msg.content }}</span>
                    <div v-else class="markdown-body" v-html="renderMarkdown(msg.content)"></div>
                  </template>
                  <span v-else class="inline-flex items-center gap-1 text-gray-400">
                    <span class="h-2 w-2 animate-pulse rounded-full bg-primary-400"></span>
                    <span class="h-2 w-2 animate-pulse rounded-full bg-primary-400 [animation-delay:0.2s]"></span>
                    <span class="h-2 w-2 animate-pulse rounded-full bg-primary-400 [animation-delay:0.4s]"></span>
                    {{ t('chat.thinking') }}
                  </span>
                </div>
                <button
                  v-if="msg.role === 'assistant' && msg.content && showAvatar"
                  @click="speaking ? stopSpeaking() : speakText(msg.content)"
                  class="mt-1 flex items-center gap-1 text-xs text-gray-400 transition hover:text-primary-600"
                >
                  <svg viewBox="0 0 24 24" class="h-3 w-3" fill="none" stroke="currentColor" stroke-width="2">
                    <path v-if="!speaking" stroke-linecap="round" stroke-linejoin="round" d="M15.536 8.464a5 5 0 010 7.072M17.95 6.05a8 8 0 010 11.9M5 9v6h4l5 4V5L9 9H5z" />
                    <path v-else stroke-linecap="round" stroke-linejoin="round" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0zM9 9h6v6H9z" />
                  </svg>
                  {{ speaking ? t('chat.stopRead') : t('chat.readAloud') }}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 输入区 -->
      <div
        v-if="hasConversation"
        class="border-t border-primary-100/60 bg-white/60 px-4 py-3 backdrop-blur safe-area-bottom"
      >
        <div class="mx-auto flex max-w-3xl items-end gap-2">
          <textarea
            v-model="input"
            @keydown="onKeydown"
            :placeholder="listening ? t('chat.listening') : t('chat.placeholder')"
            rows="1"
            class="max-h-32 flex-1 resize-none rounded-xl border border-primary-200 bg-white px-4 py-2.5 text-sm min-h-[44px] focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100"
          />
          <button
            v-if="showAvatar"
            @click="toggleMic"
            :class="[
              'flex h-11 w-11 shrink-0 items-center justify-center rounded-xl transition',
              listening ? 'bg-red-500 text-white animate-pulse' : 'border border-primary-200 bg-white text-primary-600 hover:bg-primary-50',
            ]"
            :title="t('chat.mic')"
          >
            <svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M19 11a7 7 0 01-14 0m7 7v3m-4 0h8m-4-7a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" /></svg>
          </button>
          <button
            v-if="store.streaming"
            @click="handleStop"
            class="btn-ghost !rounded-xl !px-4 !py-2.5 !text-red-600 hover:!bg-red-50"
            title="停止生成"
          >
            <svg viewBox="0 0 24 24" class="h-5 w-5" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2" /></svg>
          </button>
          <button
            v-else
            @click="handleSend"
            :disabled="!input.trim()"
            class="btn-primary !rounded-xl !px-4 !py-2.5"
          >
            <svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" /></svg>
          </button>
        </div>
      </div>
    </main>

    <!-- 浮动具身交互智能体容器：单一 DOM，通过 CSS 切换位置/大小 -->
    <div
      v-if="showAvatar"
      :class="[
        'avatar-float',
        isNarrow || isFullscreen ? 'avatar-float--full' : 'avatar-float--side',
      ]"
    >
      <!-- 具身交互智能体舞台：侧栏模式自适应，全屏模式使用 flex: 1 -->
      <div
        ref="avatarStageEl"
        class="avatar-stage relative overflow-hidden"
        :class="{ 'flex-1 min-h-0': isNarrow || isFullscreen }"
      >
        <div id="chat-avatar-container" class="h-full w-full"></div>

        <!-- 加载中遮罩 -->
        <div v-if="avatarLoading" class="absolute inset-0 flex flex-col items-center justify-center bg-white/60 backdrop-blur">
          <div class="h-8 w-8 animate-spin rounded-full border-2 border-primary-200 border-t-primary-600"></div>
          <p class="mt-3 text-xs text-gray-500">{{ t('chat.avatarLoading') }}</p>
        </div>

        <!-- 失败遮罩 -->
        <div v-else-if="avatarFailed" class="absolute inset-0 flex flex-col items-center justify-center p-4 text-center">
          <p class="text-xs text-gray-400">{{ t('chat.avatarFailed') }}</p>
        </div>
      </div>

      <!-- SDK 字幕代理渲染：移至 avatar-float 层级，避免被具身交互智能体 canvas 遮挡 -->
      <transition name="fade-up">
        <div
          v-if="sdkSubtitleVisible && sdkSubtitleText && (isNarrow || isFullscreen)"
          class="sdk-subtitle pointer-events-none absolute left-1/2 z-[100] max-w-[80%] -translate-x-1/2 rounded-2xl bg-white/90 px-4 py-2 text-center text-sm text-gray-800 shadow"
          :class="isFullscreen ? 'bottom-40' : 'bottom-32'"
        >
          {{ sdkSubtitleText }}
        </div>
      </transition>

      <!-- 控制栏：宽屏侧栏模式 -->
      <template v-if="!isNarrow && !isFullscreen">
        <div class="avatar-controls mt-2 flex items-center justify-between">
          <p class="text-sm font-semibold text-gray-700">{{ t('chat.avatarPanel') }}</p>
          <div class="flex items-center gap-2">
            <label class="flex cursor-pointer items-center gap-1.5 text-xs text-gray-500">
              <input type="checkbox" v-model="autoSpeak" class="h-3.5 w-3.5 rounded border-primary-300 text-primary-600 focus:ring-primary-400" />
              {{ t('chat.autoSpeak') }}
            </label>
            <button
              v-if="autoSpeak && store.streaming"
              type="button"
              class="rounded-full bg-red-50 px-2 py-1 text-xs font-medium text-red-600 transition hover:bg-red-100"
              @click="stopSpeaking()"
            >
              ⏹ 打断
            </button>
            <button
              type="button"
              class="rounded-full bg-primary-50 px-2 py-1 text-xs font-medium text-primary-600 transition hover:bg-primary-100"
              title="全屏具身交互智能体"
              @click="enterFullscreen"
            >
              ⤢ 全屏
            </button>
          </div>
        </div>
        <p class="mt-1 text-center text-xs text-gray-400">{{ t('chat.avatarHint') }}</p>
      </template>

      <!-- 控制栏：全屏/窄屏模式 (flex 布局，不绝对定位) -->
      <template v-else>
        <!-- 顶栏 -->
        <div class="avatar-topbar flex shrink-0 items-center justify-between border-b border-gray-100 px-4 py-3">
          <button
            @click="isFullscreen ? exitFullscreen() : toggleAvatar()"
            class="flex h-10 items-center gap-2 rounded-full bg-gray-100 px-4 text-sm font-medium text-gray-700 transition hover:bg-gray-200"
          >
            <svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" :d="isFullscreen ? 'M6 18L18 6M6 6l12 12' : 'M19 9l-7 7-7-7'"/></svg>
            {{ isFullscreen ? '退出全屏' : '关闭具身交互智能体' }}
          </button>
          <span class="text-sm font-medium text-gray-700">{{ t('chat.avatarPanel') }}</span>
          <div class="flex items-center gap-2">
            <label class="flex cursor-pointer items-center gap-1 text-xs text-gray-500">
              <input type="checkbox" v-model="autoSpeak" class="h-3.5 w-3.5 rounded border-gray-300 text-primary-600" />
              {{ t('chat.autoSpeak') }}
            </label>
          </div>
        </div>

        <!-- 底部控制区 (flex 布局，不绝对定位) -->
        <div class="avatar-bottom flex shrink-0 flex-col items-center gap-3 border-t border-gray-100 px-4 pt-4 pb-4">
          <!-- 按钮组 -->
          <div class="flex items-center justify-center gap-4">
            <!-- 停止按钮: 流式生成中时显示 -->
            <button
              v-if="store.streaming"
              type="button"
              @click="handleStop"
              class="flex h-14 w-14 items-center justify-center rounded-full bg-red-500 text-white shadow-lg transition hover:bg-red-600"
            >
              <svg viewBox="0 0 24 24" class="h-6 w-6" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2" /></svg>
            </button>

            <!-- 麦克风按钮: 全屏为持续监听开关，窄屏为 push-to-talk -->
            <button
              v-else
              type="button"
              @click="isFullscreen ? toggleFullscreenListening() : toggleMic()"
              :class="[
                'flex h-16 w-16 items-center justify-center rounded-full shadow-lg transition',
                listening ? 'bg-red-500 text-white animate-pulse' : 'bg-primary-500 text-white hover:bg-primary-600',
              ]"
            >
              <svg viewBox="0 0 24 24" class="h-7 w-7" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M19 11a7 7 0 01-14 0m7 7v3m-4 0h8m-4-7a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" /></svg>
            </button>

            <!-- 发送按钮: 所有模式均保留，用于键盘输入发送 -->
            <button
              type="button"
              @click="handleSend"
              :disabled="!input.trim()"
              class="flex h-14 w-14 items-center justify-center rounded-full bg-primary-500 text-white shadow-lg transition hover:bg-primary-600 disabled:opacity-50"
            >
              <svg viewBox="0 0 24 24" class="h-6 w-6" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" /></svg>
            </button>
          </div>

          <!-- ASR 识别文字提示: 全屏监听中且有识别结果时显示 -->
          <div v-if="isFullscreen && listening && fullscreenPartialText && !store.streaming" class="text-center text-xs text-gray-500">
            <span class="mr-1 inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-primary-400"></span>
            正在聆听: {{ fullscreenPartialText }}
          </div>

          <!-- 输入框（全屏模式专用） -->
          <div v-if="isFullscreen" class="w-full">
            <textarea
              v-model="input"
              @keydown="onKeydown"
              :placeholder="listening ? '聆听中... 直接说话或输入文字' : t('chat.placeholder')"
              rows="1"
              class="w-full resize-none rounded-xl border border-gray-200 bg-white px-4 py-3 text-sm text-gray-800 placeholder-gray-400 focus:border-primary-400 focus:outline-none"
            />
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
/* 浮动具身交互智能体容器 - 侧栏模式（宽屏） */
.avatar-float--side {
  position: relative;
  width: 320px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 16px;
  border-left: 1px solid rgba(229, 231, 235, 0.6);
  background: rgba(255, 255, 255, 0.6);
  backdrop-filter: blur(10px);
  z-index: 10;
}

.avatar-float--side .avatar-stage {
  width: 100%;
  max-height: 100%;
  flex: 1;
  aspect-ratio: 9/16;
}

/* 浮动具身交互智能体容器 - 全屏/窄屏模式 */
.avatar-float--full {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: flex;
  flex-direction: column;
  background: #ffffff;
}

/* 全屏下舞台使用 flex-1 自适应 */
.avatar-float--full .avatar-stage {
  z-index: 0;
}

/* 字幕淡入/淡出动画 */
.fade-up-enter-active,
.fade-up-leave-active {
  transition: all 0.3s ease;
}
.fade-up-enter-from {
  opacity: 0;
  transform: translate(-50%, 8px);
}
.fade-up-leave-to {
  opacity: 0;
  transform: translate(-50%, -8px);
}

/* SDK 字幕代理渲染定位 - 基于 avatar-float 容器 */
.sdk-subtitle.bottom-32 {
  bottom: 8rem;
}
.sdk-subtitle.bottom-40 {
  bottom: 10rem;
}
</style>
