<script setup lang="ts">
import { onMounted, onUnmounted, ref, nextTick, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useChatStore } from '@/stores/chat'
import { useAvatar } from '@/composables/useAvatar'
import { renderMarkdown } from '@/utils/markdown'

const { t } = useI18n()
const store = useChatStore()
const { initAvatar, getProvider, destroyAvatar } = useAvatar()

const input = ref('')
const messagesEl = ref<HTMLElement | null>(null)
const showAvatar = ref(false)
const editingId = ref<number | null>(null)
const editingTitle = ref('')

// 数字人状态
const avatarLoading = ref(false)
const avatarFailed = ref(false)
const autoSpeak = ref(true)
const listening = ref(false)
const speaking = ref(false)
const speakBuffer = ref('')
const streamAborted = ref(false)

// 全屏状态
const avatarStageEl = ref<HTMLElement | null>(null)
const isFullscreen = ref(false)
const fullscreenPartialText = ref('')

const hasConversation = computed(() => store.currentId !== null)

/** 最新一条 assistant 消息内容（全屏字幕用） */
const latestAssistantText = computed(() => {
  const msgs = store.currentMessages
  for (let i = msgs.length - 1; i >= 0; i--) {
    if (msgs[i].role === 'assistant') return msgs[i].content
  }
  return ''
})

function handleFullscreenChange() {
  isFullscreen.value = !!document.fullscreenElement
  if (!isFullscreen.value) {
    // 退出全屏时停止 ASR
    stopListening()
    fullscreenPartialText.value = ''
  }
}

onMounted(() => {
  store.fetchConversations()
  document.addEventListener('fullscreenchange', handleFullscreenChange)
})

onUnmounted(() => {
  // 离开页面清理数字人
  stopSpeaking()
  stopListening()
  destroyAvatar()
  document.removeEventListener('fullscreenchange', handleFullscreenChange)
  if (document.fullscreenElement) document.exitFullscreen()
})

// 流式输出时持续滚动到底部
watch(
  () => store.currentMessages.map((m) => m.content).join(''),
  () => scrollToBottom(),
)

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
  streamAborted.value = false
  // 开始新回答前打断上一轮播报，并开启新的流式播报会话
  if (autoSpeak.value) {
    stopSpeaking()
    getProvider()?.startSpeakStream?.()
  }
  await store.sendMessage(msg, (delta) => feedSpeak(delta))
  // 用户主动打断则不再发送结束帧（避免 interrupt 后又触发一次 speak）
  if (autoSpeak.value && !streamAborted.value) endSpeak()
  streamAborted.value = false
  scrollToBottom()
}

/** 中断当前回答生成（同时停止数字人播报），保留已生成内容 */
function handleStop() {
  streamAborted.value = true
  speakBuffer.value = ''
  store.stopGeneration()
  if (autoSpeak.value) stopSpeaking()
}

async function toggleAvatar() {
  if (showAvatar.value) {
    // 关闭：清理
    stopSpeaking()
    stopListening()
    await destroyAvatar()
    showAvatar.value = false
    avatarFailed.value = false
    return
  }
  showAvatar.value = true
  avatarLoading.value = true
  avatarFailed.value = false
  await nextTick()
  try {
    await initAvatar('chat-avatar-container')
  } catch (e) {
    console.warn('[Chat Avatar] init failed:', e)
    avatarFailed.value = true
  } finally {
    avatarLoading.value = false
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
  provider.interrupt?.()
  speaking.value = false
}

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
      input.value = (input.value + ' ' + result.text).trim()
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

/** 进入数字人全屏 */
async function enterFullscreen() {
  try {
    await avatarStageEl.value?.requestFullscreen()
  } catch (e) {
    console.warn('[Chat Fullscreen] request failed:', e)
  }
}

/** 退出数字人全屏 */
function exitFullscreen() {
  if (document.fullscreenElement) {
    document.exitFullscreen()
  }
}

/** 全屏下的麦克风：ASR final 后自动发送 */
function toggleFullscreenMic() {
  if (listening.value) {
    stopListening()
    fullscreenPartialText.value = ''
    return
  }
  const provider = getProvider()
  if (!provider || !provider.isReady()) return
  listening.value = true
  fullscreenPartialText.value = ''
  provider.startASR((result) => {
    if (result.isFinal && result.text) {
      const msg = result.text.trim()
      if (msg && !store.streaming) {
        fullscreenPartialText.value = ''
        listening.value = false
        sendFullscreenMessage(msg)
      }
    } else {
      fullscreenPartialText.value = result.text
    }
  }).catch(() => {
    listening.value = false
  })
}

/** 全屏下直接发送消息（不经 input 中转） */
async function sendFullscreenMessage(msg: string) {
  streamAborted.value = false
  if (autoSpeak.value) {
    stopSpeaking()
    getProvider()?.startSpeakStream?.()
  }
  await store.sendMessage(msg, (delta) => feedSpeak(delta))
  if (autoSpeak.value && !streamAborted.value) endSpeak()
  streamAborted.value = false
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
  <div class="flex h-[calc(100vh-4rem)] overflow-hidden">
    <!-- 左：会话列表 -->
    <aside class="hidden w-64 shrink-0 flex-col border-r border-primary-100/60 bg-white/60 backdrop-blur md:flex">
      <div class="p-3">
        <button class="btn-primary w-full !py-2 text-sm" @click="handleNew">
          <svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4" /></svg>
          {{ t('chat.newConversation') }}
        </button>
      </div>
      <div class="flex-1 overflow-y-auto px-2 pb-3">
        <button
          v-for="conv in store.conversations"
          :key="conv.id"
          @click="store.selectConversation(conv.id)"
          :class="[
            'group mb-1 flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm transition',
            store.currentId === conv.id ? 'bg-primary-50 text-primary-700' : 'text-gray-600 hover:bg-primary-50/50',
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
          <span v-if="editingId !== conv.id" class="hidden shrink-0 gap-1 group-hover:flex">
            <button @click.stop="startRename(conv.id, conv.title)" class="text-gray-400 hover:text-primary-600" :title="t('chat.rename')">
              <svg viewBox="0 0 24 24" class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" /></svg>
            </button>
            <button @click.stop="handleDelete(conv.id)" class="text-gray-400 hover:text-red-600" :title="t('chat.delete')">
              <svg viewBox="0 0 24 24" class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
            </button>
          </span>
        </button>
        <p v-if="store.conversations.length === 0" class="px-3 py-6 text-center text-xs text-gray-400">{{ t('chat.empty') }}</p>
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
          <button class="btn-primary mt-6" @click="handleNew">{{ t('chat.newConversation') }}</button>
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
                    'rounded-2xl px-4 py-2.5 text-sm leading-relaxed shadow-soft',
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
      <div v-if="hasConversation" class="border-t border-primary-100/60 bg-white/60 px-4 py-3 backdrop-blur">
        <div class="mx-auto flex max-w-3xl items-end gap-2">
          <textarea
            v-model="input"
            @keydown="onKeydown"
            :placeholder="listening ? t('chat.listening') : t('chat.placeholder')"
            rows="1"
            class="max-h-32 flex-1 resize-none rounded-xl border border-primary-200 bg-white px-4 py-2.5 text-sm focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100"
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

    <!-- 右：数字人侧栏（TTS 播报 / ASR 输入） -->
    <aside v-if="showAvatar" class="hidden w-80 shrink-0 flex-col border-l border-primary-100/60 bg-white/60 p-4 backdrop-blur lg:flex">
      <div class="mb-3 flex items-center justify-between">
        <p class="text-sm font-semibold text-gray-700">{{ t('chat.avatarPanel') }}</p>
        <div class="flex items-center gap-3">
          <label class="flex cursor-pointer items-center gap-1.5 text-xs text-gray-500">
            <input type="checkbox" v-model="autoSpeak" class="h-3.5 w-3.5 rounded border-primary-300 text-primary-600 focus:ring-primary-400" />
            {{ t('chat.autoSpeak') }}
          </label>
          <button
            v-if="autoSpeak && store.streaming"
            type="button"
            class="rounded-full bg-red-50 px-2.5 py-1 text-xs font-medium text-red-600 transition hover:bg-red-100"
            @click="stopSpeaking()"
          >
            ⏹ 打断播报
          </button>
          <!-- 全屏按钮 -->
          <button
            v-if="!isFullscreen"
            type="button"
            class="rounded-full bg-primary-50 px-2.5 py-1 text-xs font-medium text-primary-600 transition hover:bg-primary-100"
            title="全屏数字人"
            @click="enterFullscreen"
          >
            ⤢ 全屏
          </button>
        </div>
      </div>

      <!-- 数字人舞台（可全屏） -->
      <div
        ref="avatarStageEl"
        class="avatar-stage relative flex-1 overflow-hidden rounded-2xl border border-primary-100/60 bg-gradient-brand-soft"
      >
        <div id="chat-avatar-container" class="h-full w-full"></div>
        <div v-if="avatarLoading" class="absolute inset-0 flex flex-col items-center justify-center bg-white/60 backdrop-blur">
          <div class="h-8 w-8 animate-spin rounded-full border-2 border-primary-200 border-t-primary-600"></div>
          <p class="mt-3 text-xs text-gray-500">{{ t('chat.avatarLoading') }}</p>
        </div>
        <div v-else-if="avatarFailed" class="absolute inset-0 flex flex-col items-center justify-center p-4 text-center">
          <span class="mb-3 flex h-14 w-14 items-center justify-center rounded-full bg-primary-100 text-primary-500">
            <svg viewBox="0 0 24 24" class="h-7 w-7" fill="none" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" /></svg>
          </span>
          <p class="text-xs text-gray-400">{{ t('chat.avatarFailed') }}</p>
        </div>

        <!-- 全屏模式浮层 -->
        <template v-if="isFullscreen">
          <!-- 退出按钮 -->
          <button
            type="button"
            class="absolute right-4 top-4 z-20 flex h-10 w-10 items-center justify-center rounded-full bg-white/80 text-gray-600 shadow-soft transition hover:bg-white"
            title="退出全屏（ESC）"
            @click="exitFullscreen"
          >
            <svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>
          </button>

          <!-- 底部字幕浮层 -->
          <div class="absolute inset-x-0 bottom-0 z-10 bg-gradient-to-t from-black/70 via-black/40 to-transparent px-6 pb-6 pt-16">
            <!-- 上行：ASR 实时字幕 -->
            <div v-if="fullscreenPartialText || listening" class="mb-3 text-right">
              <p class="mb-1 text-xs text-white/60">🎤 {{ listening ? '正在聆听...' : '语音输入' }}</p>
              <p class="ml-auto max-w-2xl rounded-2xl rounded-br-sm bg-white/20 px-4 py-2 text-sm text-white backdrop-blur">
                {{ fullscreenPartialText || '...' }}
              </p>
            </div>

            <!-- 下行：数字人最新消息字幕 -->
            <div v-if="latestAssistantText" class="mb-4">
              <p class="mb-1 text-xs text-white/60">💬 数字人</p>
              <p class="max-w-2xl rounded-2xl rounded-bl-sm bg-white/90 px-4 py-2 text-sm leading-relaxed text-gray-800 backdrop-blur">
                {{ latestAssistantText }}
              </p>
            </div>

            <!-- 麦克风按钮 + 停止生成 -->
            <div class="flex items-center justify-center gap-4">
              <button
                v-if="store.streaming"
                type="button"
                @click="handleStop"
                class="flex h-14 w-14 items-center justify-center rounded-full bg-red-500 text-white shadow-lg transition hover:bg-red-600"
                title="停止生成"
              >
                <svg viewBox="0 0 24 24" class="h-6 w-6" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2" /></svg>
              </button>
              <button
                v-else
                type="button"
                @click="toggleFullscreenMic"
                :class="[
                  'flex h-14 w-14 items-center justify-center rounded-full shadow-lg transition',
                  listening ? 'bg-red-500 text-white animate-pulse' : 'bg-white text-primary-600 hover:bg-primary-50',
                ]"
                :title="listening ? '停止语音输入' : '开始语音输入'"
              >
                <svg viewBox="0 0 24 24" class="h-6 w-6" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M19 11a7 7 0 01-14 0m7 7v3m-4 0h8m-4-7a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" /></svg>
              </button>
            </div>
          </div>
        </template>
      </div>
      <p v-if="!isFullscreen" class="mt-2 text-center text-xs text-gray-400">{{ t('chat.avatarHint') }}</p>
    </aside>
  </div>
</template>
