<script setup lang="ts">
import { onMounted, onUnmounted, ref, computed, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { VueMonacoEditor } from '@guolao/vue-monaco-editor'
import { useInterviewStore } from '@/stores/interview'
import { useAvatar } from '@/composables/useAvatar'
import { useDevice } from '@/composables/useDevice'
import { useMediaRecorder } from '@/composables/useMediaRecorder'
import { WebSpeechAsrProvider } from '@/providers/webSpeechAsrProvider'
import { getLanguages, type LanguageItem } from '@/api/code'
import { renderMarkdown } from '@/utils/markdown'
import type { ASRResult } from '@/types'
import type { AvatarProvider } from '@/providers/avatarProvider'

const { t } = useI18n()
const router = useRouter()
const store = useInterviewStore()
const { initAvatar, getProvider, destroyAvatar, isDigital } = useAvatar()
const { isMobile, isLandscape } = useDevice()

const chatPanel = ref<HTMLElement | null>(null)
const textInput = ref('')
const inputMode = ref<'voice' | 'text'>('voice')
const isListening = ref(false)
const partialText = ref('')
const asrResults = ref('')
const avatarContainerId = 'avatar-container'
const initializing = ref(true)
const avatarProvider = ref<AvatarProvider | null>(null)
const fallbackAsr = ref<WebSpeechAsrProvider | null>(null)
let timer: ReturnType<typeof setInterval> | null = null

// 摄像头 PiP 小窗
const cameraVideoRef = ref<HTMLVideoElement | null>(null)
const cameraStream = ref<MediaStream | null>(null)
const cameraEnabled = ref(false)
const cameraCollapsed = ref(false)

// 算法题代码编辑器
const codeLang = ref('python')
const codeValue = ref('')
const codeLanguages = ref<LanguageItem[]>([])
const codeSubmitting = ref(false)
const codePanelCollapsed = ref(false)

const monacoLangMap: Record<string, string> = {
  python: 'python', javascript: 'javascript', typescript: 'typescript',
  java: 'java', cpp: 'cpp', c: 'c', go: 'go', rust: 'rust',
}

// 加载语言列表
;(async () => {
  try {
    codeLanguages.value = await getLanguages()
    if (codeLanguages.value.length > 0) {
      codeValue.value = codeLanguages.value[0].template
    }
  } catch { /* ignore */ }
})()

// 面试录制
const useRecorder = () => {
  const recorder = useMediaRecorder(
    computed(() => store.interviewId),
    { streamType: 'audio' },
  )
  const recordingEnabled = ref(false)

  watch(() => store.state, (newState) => {
    if (newState === 'generating_report' && recordingEnabled.value) {
      recorder.flush()
    }
  })

  return { ...recorder, recordingEnabled }
}

const {
  durationMs: recorderDuration,
  isRecording: isRecorderOn,
  recordingEnabled,
  start: startRecorder,
  stop: stopRecorder,
  flush: flushRecorder,
} = useRecorder()

// 当切换到算法题时，重置代码
watch(() => store.currentProblem, (problem) => {
  if (problem) {
    const lang = codeLanguages.value.find((l) => l.id === codeLang.value)
    codeValue.value = lang?.template || ''
    codePanelCollapsed.value = false
  }
})

function onCodeLangChange() {
  const lang = codeLanguages.value.find((l) => l.id === codeLang.value)
  if (lang) codeValue.value = lang.template
}

async function submitCode() {
  if (!store.currentProblem || !codeValue.value.trim()) return
  codeSubmitting.value = true
  try {
    await store.submitCode(store.currentProblem.id, codeLang.value, codeValue.value)
    await nextTick()
    scrollToBottom()
    await speakCurrentQuestion()
  } catch (e: any) {
    alert(e.message)
  } finally {
    codeSubmitting.value = false
  }
}

async function startCamera() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 320 }, height: { ideal: 240 } },
      audio: false,
    })
    cameraStream.value = stream
    cameraEnabled.value = true
    await nextTick()
    if (cameraVideoRef.value) {
      cameraVideoRef.value.srcObject = stream
    }
  } catch (e: any) {
    console.warn('[Interview] camera start failed:', e)
    cameraEnabled.value = false
  }
}

function stopCamera() {
  if (cameraStream.value) {
    cameraStream.value.getTracks().forEach((t) => t.stop())
    cameraStream.value = null
  }
  cameraEnabled.value = false
}

const remainingDisplay = computed(() => {
  const sec = store.remainingTime
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return `${m}:${s.toString().padStart(2, '0')}`
})

onMounted(async () => {
  if (!store.interviewId) {
    router.replace('/setup')
    return
  }

  await nextTick()
  console.log(document.getElementById(avatarContainerId))

  try {
    avatarProvider.value = await initAvatar(avatarContainerId)
    const provider = getProvider()
    if (provider) {
      await speakCurrentQuestion()
    }
  } catch (e: any) {
    console.error('[Interview] avatar init failed:', e)
  } finally {
    initializing.value = false
  }

  fallbackAsr.value = new WebSpeechAsrProvider()

  // 启动摄像头（失败不阻塞面试）
  startCamera()

  timer = setInterval(() => {
    if (store.remainingTime <= 0 && store.isRunning) {
      store.endInterview()
      clearInterval(timer!)
      timer = null
    }
  }, 1000)
})

onUnmounted(async () => {
  if (timer) clearInterval(timer)
  stopCamera()
  await destroyAvatar()
})

async function speakCurrentQuestion() {
  const provider = getProvider()
  if (!provider || store.messages.length === 0) return
  const lastMsg = store.messages[store.messages.length - 1]
  if (lastMsg.role === 'interviewer') {
    store.setState('asking')
    await provider.speak(lastMsg.content)
    store.setState('waiting_answer')
  }
}

async function startVoice() {
  const provider = getProvider()
  if (!provider) return

  isListening.value = true
  asrResults.value = ''
  partialText.value = ''

  if (isDigital.value && provider) {
    await provider.startASR((result: ASRResult) => {
      if (result.isFinal) {
        asrResults.value += result.text
        partialText.value = ''
      } else {
        partialText.value = result.text
      }
    })
  } else if (fallbackAsr.value && fallbackAsr.value.isAvailable()) {
    fallbackAsr.value.start((result: ASRResult) => {
      if (result.isFinal) {
        asrResults.value += result.text
        partialText.value = ''
      } else {
        partialText.value = result.text
      }
    })
  } else {
    alert(t('interview.asrUnsupported'))
    isListening.value = false
  }
}

async function stopVoice() {
  isListening.value = false
  const provider = getProvider()
  if (isDigital.value && provider) {
    await provider.stopASR()
  } else if (fallbackAsr.value) {
    fallbackAsr.value.stop()
  }
  const finalText = asrResults.value.trim()
  if (finalText) {
    await submitAnswer(finalText)
  }
  asrResults.value = ''
  partialText.value = ''
}

async function submitText() {
  const text = textInput.value.trim()
  if (!text) return
  textInput.value = ''
  await submitAnswer(text)
}

async function submitAnswer(text: string) {
  await store.submitAnswer(text)
  await nextTick()
  scrollToBottom()
  await speakCurrentQuestion()
}

const isEnding = ref(false)

async function handleEnd() {
  if (isEnding.value) return
  isEnding.value = true

  const farewell = t('interview.farewell')
  store.addMessage('interviewer', farewell)

  const provider = getProvider()
  if (provider) {
    store.setState('asking')
    await provider.speak(farewell)
  }

  await store.endInterview()
  if (store.interviewId) {
    router.push(`/report/${store.interviewId}`)
  }
}

async function handleInterrupt() {
  const provider = getProvider()
  if (provider) {
    await provider.interrupt()
  }
}

function scrollToBottom() {
  if (chatPanel.value) {
    chatPanel.value.scrollTop = chatPanel.value.scrollHeight
  }
}
</script>

<template>
  <div class="flex h-screen flex-col bg-gray-50">
    <div class="flex items-center justify-between border-b bg-white px-4 py-3">
      <div>
        <p class="font-semibold text-gray-800 text-sm md:text-base">
          {{ store.config ? t('positions.' + store.config.position, store.config.position) : '' }} ·
          {{ store.config ? t('difficulty.' + store.config.difficulty, store.config.difficulty) : '' }}
        </p>
        <p class="text-xs text-gray-400 hidden md:block">{{ store.config?.style ? t('styles.' + store.config.style, store.config.style) : '' }}</p>
      </div>
      <div class="flex items-center gap-3 md:gap-4">
        <div class="text-base md:text-lg font-mono" :class="store.remainingTime < 60 ? 'text-red-500' : 'text-gray-600'">
          {{ remainingDisplay }}
        </div>
        <button
          @click="handleEnd"
          :disabled="isEnding || store.state === 'generating_report'"
          class="rounded-lg bg-red-500 px-3 md:px-4 py-2 text-xs md:text-sm text-white hover:bg-red-600 disabled:opacity-50 min-h-[44px]"
        >
          {{ isEnding ? t('interview.ending') : t('interview.endInterview') }}
        </button>
      </div>
    </div>

    <div class="flex flex-1 overflow-hidden flex-col md:flex-row" :class="{ 'md:flex-row': isMobile && isLandscape }">
      <div class="flex h-40 md:h-full md:w-2/5 flex-shrink-0 flex-col items-center justify-center border-b md:border-b-0 md:border-r p-2" :class="{ 'md:w-1/3': isMobile && isLandscape }">
        <div
          class="avatar-stage relative max-h-full w-full overflow-hidden rounded-2xl border border-primary-100/60 bg-gradient-brand-soft"
          :id="avatarContainerId"
        >
          <div v-if="initializing" class="flex h-full items-center justify-center text-gray-400">
            <div class="text-center">
              <div class="mx-auto mb-3 h-8 w-8 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600"></div>
              <p class="text-sm">{{ t('interview.avatarInit') }}</p>
            </div>
          </div>
        </div>
      </div>

      <div class="flex flex-1 flex-col">
        <div ref="chatPanel" class="flex-1 overflow-y-auto p-4 space-y-3">
          <div
            v-for="msg in store.messages"
            :key="msg.id"
            :class="[
              'flex',
              msg.role === 'interviewer' ? 'justify-start' : 'justify-end',
            ]"
          >
            <div
              :class="[
                'max-w-[80%] rounded-lg px-4 py-2 text-sm',
                msg.role === 'interviewer'
                  ? 'bg-white text-gray-800 shadow-sm'
                  : 'bg-primary-600 text-white',
              ]"
            >
              {{ msg.content }}
            </div>
          </div>
          <div v-if="store.state === 'analyzing'" class="flex justify-start">
            <div class="rounded-lg bg-white px-4 py-2 text-sm text-gray-400 shadow-sm">
              <span class="animate-pulse">{{ t('interview.analyzing') }}</span>
            </div>
          </div>
          <div v-if="store.state === 'generating_report'" class="flex justify-start">
            <div class="rounded-lg bg-white px-4 py-2 text-sm text-gray-400 shadow-sm">
              <span class="animate-pulse">{{ t('interview.generatingReport') }}</span>
            </div>
          </div>
        </div>

        <div class="border-t bg-white p-3 md:p-4 safe-area-bottom">
          <!-- 算法题代码编辑器面板 -->
          <div v-if="store.currentProblem" class="mb-3 rounded-lg border border-primary-200 bg-primary-50/30">
            <div class="flex items-center justify-between border-b border-primary-100 px-3 py-2">
              <div class="flex items-center gap-2">
                <span class="text-sm font-semibold text-primary-700">{{ store.currentProblem.title }}</span>
                <span class="rounded px-1.5 py-0.5 text-xs"
                  :class="store.currentProblem.difficulty === '简单' ? 'bg-green-100 text-green-700' : store.currentProblem.difficulty === '中等' ? 'bg-yellow-100 text-yellow-700' : 'bg-red-100 text-red-700'">
                  {{ store.currentProblem.difficulty }}
                </span>
              </div>
              <button @click="codePanelCollapsed = !codePanelCollapsed" class="text-xs text-gray-500 hover:text-gray-700">
                {{ codePanelCollapsed ? '展开' : '收起' }}
              </button>
            </div>
            <div v-show="!codePanelCollapsed" class="p-3">
              <div class="markdown-body mb-2 max-h-32 overflow-y-auto text-xs text-gray-700" v-html="renderMarkdown(store.currentProblem.description)"></div>
              <div class="mb-2 flex items-center gap-2">
                <select v-model="codeLang" @change="onCodeLangChange"
                  class="rounded border border-gray-300 px-2 py-1 text-xs focus:border-primary-500 focus:outline-none">
                  <option v-for="lang in codeLanguages" :key="lang.id" :value="lang.id">{{ lang.label }}</option>
                </select>
                <button @click="submitCode" :disabled="codeSubmitting || store.state !== 'waiting_answer'"
                  class="ml-auto rounded bg-primary-600 px-3 py-1 text-xs text-white hover:bg-primary-700 disabled:opacity-50">
                  {{ codeSubmitting ? '判定中...' : '提交代码' }}
                </button>
              </div>
              <div class="h-40 md:h-48 overflow-hidden rounded border border-gray-200">
                <VueMonacoEditor :value="codeValue" :language="monacoLangMap[codeLang] || 'plaintext'" theme="vs"
                  :options="{ minimap: { enabled: false }, fontSize: 13, scrollBeyondLastLine: false, automaticLayout: true }"
                  @update:value="(val: string) => (codeValue = val)" />
              </div>
              <!-- 上次判定结果 -->
              <div v-if="store.lastJudgeResult" class="mt-2 rounded bg-gray-50 p-2 text-xs">
                <span :class="store.lastJudgeResult.status === 'accepted' ? 'text-green-600' : 'text-red-600'" class="font-semibold">
                  {{ store.lastJudgeResult.status === 'accepted' ? '✓ 通过' : '✗ ' + store.lastJudgeResult.status }}
                </span>
                <span class="ml-2 text-gray-500">{{ store.lastJudgeResult.passCount }}/{{ store.lastJudgeResult.totalCount }} 用例</span>
              </div>
            </div>
          </div>

          <div v-if="isListening" class="mb-2 rounded-lg bg-primary-50 px-3 py-2 text-sm text-primary-700">
            <span class="animate-pulse">🎤 {{ t('interview.listening') }} </span>
            <span v-if="partialText">{{ partialText }}</span>
            <span v-else-if="asrResults">{{ asrResults }}</span>
          </div>

          <div class="flex flex-wrap gap-2">
            <!-- 录制开关 -->
            <button
              v-if="!recordingEnabled"
              @click="recordingEnabled = true; startRecorder()"
              class="rounded-lg border border-gray-300 px-3 py-2 text-xs md:text-sm text-gray-600 hover:bg-gray-100 min-h-[44px]"
              :title="t('interview.record')"
            >
              <svg viewBox="0 0 24 24" class="h-4 w-4 inline" fill="currentColor"><circle cx="12" cy="12" r="6" fill="currentColor"/></svg>
              录制
            </button>
            <button
              v-else
              @click="recordingEnabled = false; stopRecorder(); flushRecorder()"
              class="rounded-lg border border-red-300 px-3 py-2 text-xs md:text-sm text-red-600 hover:bg-red-100 min-h-[44px]"
            >
              <svg viewBox="0 0 24 24" class="h-4 w-4 inline" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor"/></svg>
              {{ isRecorderOn ? '录制中 ' + Math.floor(recorderDuration / 1000) + 's' : '停止录制' }}
            </button>

            <button
              @click="inputMode = inputMode === 'voice' ? 'text' : 'voice'"
              class="rounded-lg border border-gray-300 px-3 py-2 text-xs md:text-sm text-gray-600 hover:bg-gray-100 min-h-[44px]"
            >
              {{ inputMode === 'voice' ? t('interview.textMode') : t('interview.voiceMode') }}
            </button>

            <template v-if="inputMode === 'voice'">
              <button
                v-if="!isListening"
                @click="startVoice"
                :disabled="store.state !== 'waiting_answer'"
                class="flex-1 rounded-lg bg-primary-600 px-3 md:px-4 py-2 text-xs md:text-sm text-white hover:bg-primary-700 disabled:opacity-50 min-h-[44px]"
              >
                {{ t('interview.startAnswer') }}
              </button>
              <button
                v-else
                @click="stopVoice"
                class="flex-1 rounded-lg bg-red-500 px-3 md:px-4 py-2 text-xs md:text-sm text-white hover:bg-red-600 min-h-[44px]"
              >
                {{ t('interview.submitAnswer') }}
              </button>
            </template>

            <template v-else>
              <input
                v-model="textInput"
                @keydown.enter="submitText"
                :disabled="store.state !== 'waiting_answer'"
                :placeholder="t('interview.inputPlaceholder')"
                class="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-xs md:text-sm focus:border-primary-500 focus:outline-none min-h-[44px]"
              />
              <button
                @click="submitText"
                :disabled="!textInput.trim() || store.state !== 'waiting_answer'"
                class="rounded-lg bg-primary-600 px-3 md:px-4 py-2 text-xs md:text-sm text-white hover:bg-primary-700 disabled:opacity-50 min-h-[44px]"
              >
                {{ t('common.send') }}
              </button>
            </template>

            <button
              @click="handleInterrupt"
              class="rounded-lg border border-gray-300 px-3 py-2 text-xs md:text-sm text-gray-600 hover:bg-gray-100 min-h-[44px]"
            >
              {{ t('common.interrupt') }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 右下角摄像头 PiP 小窗 -->
    <div
      v-if="cameraEnabled"
      class="fixed bottom-[calc(1rem+env(safe-area-inset-bottom))] md:bottom-4 right-4 z-30 overflow-hidden rounded-xl border border-white/30 bg-black shadow-xl"
    >
      <video
        v-show="!cameraCollapsed"
        ref="cameraVideoRef"
        autoplay
        playsinline
        muted
        class="h-28 w-40 object-cover"
      />
      <!-- 小窗标题栏（折叠/展开） -->
      <div class="absolute right-1 top-1 flex gap-1">
        <button
          @click="cameraCollapsed = !cameraCollapsed"
          class="flex h-6 w-6 items-center justify-center rounded bg-black/40 text-white transition hover:bg-black/60"
          :title="cameraCollapsed ? '展开' : '收起'"
        >
          <svg v-if="cameraCollapsed" viewBox="0 0 24 24" class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" /></svg>
          <svg v-else viewBox="0 0 24 24" class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M9 9V4.5M9 9H4.5M9 9L4.5 4.5M15 9h4.5M15 9V4.5M15 9l4.5-4.5M9 15v4.5M9 15H4.5M9 15l-4.5 4.5M15 15h4.5M15 15v4.5m0-4.5l4.5 4.5" /></svg>
        </button>
      </div>
      <!-- 折叠时的占位 -->
      <div v-if="cameraCollapsed" class="flex h-9 w-40 items-center justify-center bg-black px-2">
        <span class="text-xs text-white/70">摄像头已收起</span>
      </div>
    </div>
  </div>
</template>
