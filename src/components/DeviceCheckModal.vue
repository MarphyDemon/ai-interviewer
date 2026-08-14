<script setup lang="ts">
import { ref, watch, onUnmounted, nextTick } from 'vue'
import { useMediaDevices } from '@/composables/useMediaDevices'

const props = defineProps<{ visible: boolean }>()
const emit = defineEmits<{
  (e: 'close'): void
  (e: 'start'): void
}>()

const {
  videoRef,
  cameraStatus,
  micStatus,
  micLevel,
  errorMsg,
  startAll,
  stop,
} = useMediaDevices()

const testing = ref(false)

watch(
  () => props.visible,
  async (v) => {
    if (v) {
      await nextTick()
      await runTest()
    } else {
      stop()
    }
  },
)

async function runTest() {
  testing.value = true
  await startAll()
  testing.value = false
}

const allOk = () => cameraStatus.value === 'ok' && micStatus.value === 'ok'
const hasIssue = () =>
  cameraStatus.value === 'denied' ||
  cameraStatus.value === 'error' ||
  micStatus.value === 'denied' ||
  micStatus.value === 'error'

function handleStart() {
  stop()
  emit('start')
}

function handleClose() {
  stop()
  emit('close')
}

onUnmounted(() => {
  stop()
})
</script>

<template>
  <Teleport to="body">
    <div
      v-if="visible"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      @click.self="handleClose"
    >
      <div class="w-full max-w-lg rounded-2xl bg-white p-6 shadow-xl">
        <div class="mb-4 flex items-center justify-between">
          <h2 class="text-lg font-semibold text-gray-800">设备调试</h2>
          <button
            @click="handleClose"
            class="text-gray-400 transition hover:text-gray-600"
          >
            <svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        </div>

        <p class="mb-4 text-sm text-gray-500">进入面试前，请确保摄像头和麦克风正常工作。</p>

        <!-- 摄像头预览 -->
        <div class="mb-4">
          <div class="relative aspect-video w-full overflow-hidden rounded-xl border border-gray-200 bg-gray-900">
            <video
              ref="videoRef"
              autoplay
              playsinline
              muted
              class="h-full w-full object-cover"
            />
            <div v-if="cameraStatus !== 'ok'" class="absolute inset-0 flex flex-col items-center justify-center bg-gray-900/80 text-center">
              <div v-if="cameraStatus === 'loading'" class="h-8 w-8 animate-spin rounded-full border-2 border-gray-600 border-t-white"></div>
              <template v-else>
                <svg viewBox="0 0 24 24" class="mb-2 h-10 w-10 text-gray-500" fill="none" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>
                <p class="px-4 text-xs text-gray-400">
                  {{ cameraStatus === 'denied' ? '摄像头权限被拒绝' : cameraStatus === 'error' ? '摄像头启动失败' : '摄像头未启动' }}
                </p>
              </template>
            </div>
          </div>
          <div class="mt-2 flex items-center gap-2 text-sm">
            <span
              :class="[
                'inline-block h-2 w-2 rounded-full',
                cameraStatus === 'ok' ? 'bg-green-500' : cameraStatus === 'denied' || cameraStatus === 'error' ? 'bg-red-500' : 'bg-gray-300',
              ]"
            ></span>
            <span class="text-gray-600">摄像头</span>
            <span class="text-xs text-gray-400">
              {{ cameraStatus === 'ok' ? '正常' : cameraStatus === 'denied' ? '已拒绝' : cameraStatus === 'error' ? '异常' : cameraStatus === 'loading' ? '检测中...' : '未检测' }}
            </span>
          </div>
        </div>

        <!-- 麦克风音量 -->
        <div class="mb-4">
          <div class="flex items-center gap-2">
            <span
              :class="[
                'inline-block h-2 w-2 rounded-full',
                micStatus === 'ok' ? 'bg-green-500' : micStatus === 'denied' || micStatus === 'error' ? 'bg-red-500' : 'bg-gray-300',
              ]"
            ></span>
            <span class="text-sm text-gray-600">麦克风</span>
            <span class="text-xs text-gray-400">
              {{ micStatus === 'ok' ? '正常' : micStatus === 'denied' ? '已拒绝' : micStatus === 'error' ? '异常' : micStatus === 'loading' ? '检测中...' : '未检测' }}
            </span>
          </div>
          <!-- 音量条 -->
          <div class="mt-2 h-3 w-full overflow-hidden rounded-full bg-gray-200">
            <div
              class="h-full transition-all duration-75"
              :class="micLevel > 60 ? 'bg-red-500' : micLevel > 30 ? 'bg-amber-500' : 'bg-green-500'"
              :style="{ width: micLevel + '%' }"
            ></div>
          </div>
          <p class="mt-1 text-xs text-gray-400">请对麦克风说话，观察音量变化</p>
        </div>

        <!-- 错误提示 -->
        <div v-if="hasIssue() && errorMsg" class="mb-4 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-700">
          ⚠ {{ errorMsg }}。可选择「无设备继续」或重新检测。
        </div>

        <!-- 操作按钮 -->
        <div class="flex gap-2">
          <button
            @click="runTest"
            :disabled="testing"
            class="rounded-xl border border-gray-300 bg-white px-4 py-2 text-sm text-gray-700 transition hover:bg-gray-50 disabled:opacity-50"
          >
            {{ testing ? '检测中...' : '重新检测' }}
          </button>
          <button
            @click="handleClose"
            class="rounded-xl border border-gray-300 bg-white px-4 py-2 text-sm text-gray-700 transition hover:bg-gray-50"
          >
            取消
          </button>
          <div class="flex-1"></div>
          <button
            v-if="hasIssue()"
            @click="handleStart"
            class="rounded-xl border border-amber-300 bg-amber-50 px-4 py-2 text-sm text-amber-700 transition hover:bg-amber-100"
          >
            无设备继续
          </button>
          <button
            v-if="allOk()"
            @click="handleStart"
            class="btn-primary !px-6 !py-2 !text-sm"
          >
            开始面试
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
