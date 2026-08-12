<script setup lang="ts">
import { onMounted, onUnmounted, ref, computed, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useInterviewStore } from '@/stores/interview'
import { useAvatar } from '@/composables/useAvatar'
import { WebSpeechAsrProvider } from '@/providers/webSpeechAsrProvider'
import type { ASRResult } from '@/types'
import type { AvatarProvider } from '@/providers/avatarProvider'

const { t } = useI18n()
const router = useRouter()
const store = useInterviewStore()
const { initAvatar, getProvider, destroyAvatar, isDigital } = useAvatar()

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
        <p class="font-semibold text-gray-800">
          {{ store.config ? t('positions.' + store.config.position, store.config.position) : '' }} ·
          {{ store.config ? t('difficulty.' + store.config.difficulty, store.config.difficulty) : '' }}
        </p>
        <p class="text-xs text-gray-400">{{ store.config?.style ? t('styles.' + store.config.style, store.config.style) : '' }}</p>
      </div>
      <div class="flex items-center gap-4">
        <div class="text-lg font-mono" :class="store.remainingTime < 60 ? 'text-red-500' : 'text-gray-600'">
          {{ remainingDisplay }}
        </div>
        <button
          @click="handleEnd"
          :disabled="isEnding || store.state === 'generating_report'"
          class="rounded-lg bg-red-500 px-4 py-2 text-sm text-white hover:bg-red-600 disabled:opacity-50"
        >
          {{ isEnding ? t('interview.ending') : t('interview.endInterview') }}
        </button>
      </div>
    </div>

    <div class="flex flex-1 overflow-hidden flex-col md:flex-row">
      <div class="h-48 md:h-full md:w-2/5 flex-shrink-0 border-r" :id="avatarContainerId">
        <div v-if="initializing" class="flex h-full items-center justify-center text-gray-400">
          <div class="text-center">
            <div class="mx-auto mb-3 h-8 w-8 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600"></div>
            <p class="text-sm">{{ t('interview.avatarInit') }}</p>
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

        <div class="border-t bg-white p-4">
          <div v-if="isListening" class="mb-2 rounded-lg bg-primary-50 px-3 py-2 text-sm text-primary-700">
            <span class="animate-pulse">🎤 {{ t('interview.listening') }} </span>
            <span v-if="partialText">{{ partialText }}</span>
            <span v-else-if="asrResults">{{ asrResults }}</span>
          </div>

          <div class="flex gap-2">
            <button
              @click="inputMode = inputMode === 'voice' ? 'text' : 'voice'"
              class="rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-600 hover:bg-gray-100"
            >
              {{ inputMode === 'voice' ? t('interview.textMode') : t('interview.voiceMode') }}
            </button>

            <template v-if="inputMode === 'voice'">
              <button
                v-if="!isListening"
                @click="startVoice"
                :disabled="store.state !== 'waiting_answer'"
                class="flex-1 rounded-lg bg-primary-600 px-4 py-2 text-sm text-white hover:bg-primary-700 disabled:opacity-50"
              >
                {{ t('interview.startAnswer') }}
              </button>
              <button
                v-else
                @click="stopVoice"
                class="flex-1 rounded-lg bg-red-500 px-4 py-2 text-sm text-white hover:bg-red-600"
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
                class="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none"
              />
              <button
                @click="submitText"
                :disabled="!textInput.trim() || store.state !== 'waiting_answer'"
                class="rounded-lg bg-primary-600 px-4 py-2 text-sm text-white hover:bg-primary-700 disabled:opacity-50"
              >
                {{ t('common.send') }}
              </button>
            </template>

            <button
              @click="handleInterrupt"
              class="rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-600 hover:bg-gray-100"
            >
              {{ t('common.interrupt') }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
