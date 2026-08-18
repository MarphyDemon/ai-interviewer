<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'

const props = defineProps<{
  duration: number
  autoStart?: boolean
  warningThreshold?: number
}>()

const emit = defineEmits<{
  finish: []
  tick: [remaining: number]
}>()

const remaining = ref(props.duration * 60)
const isRunning = ref(false)
const intervalId = ref<number | null>(null)

const formatted = computed(() => {
  const mins = Math.floor(remaining.value / 60)
  const secs = remaining.value % 60
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
})

const isWarning = computed(() => {
  const threshold = props.warningThreshold ?? 60
  return remaining.value <= threshold && remaining.value > 0
})

const isFinished = computed(() => remaining.value <= 0)

function start() {
  if (isRunning.value || isFinished.value) return
  isRunning.value = true
  intervalId.value = window.setInterval(() => {
    remaining.value -= 1
    emit('tick', remaining.value)
    if (remaining.value <= 0) {
      stop()
      emit('finish')
    }
  }, 1000)
}

function stop() {
  isRunning.value = false
  if (intervalId.value !== null) {
    clearInterval(intervalId.value)
    intervalId.value = null
  }
}

function reset() {
  stop()
  remaining.value = props.duration * 60
}

watch(() => props.duration, () => {
  reset()
})

onMounted(() => {
  if (props.autoStart) start()
})

onUnmounted(stop)

defineExpose({ start, stop, reset, remaining, isRunning })
</script>

<template>
  <div class="flex items-center gap-2">
    <div
      :class="[
        'font-mono text-2xl font-bold tabular-nums transition-colors',
        isWarning ? 'text-red-500 animate-pulse' : isFinished ? 'text-gray-400' : 'text-gray-800',
      ]"
    >
      {{ formatted }}
    </div>
    <button
      v-if="!isRunning && !isFinished"
      @click="start"
      class="text-xs px-2 py-1 bg-blue-100 text-blue-600 rounded hover:bg-blue-200"
    >
      开始
    </button>
    <button
      v-if="isRunning"
      @click="stop"
      class="text-xs px-2 py-1 bg-gray-100 text-gray-600 rounded hover:bg-gray-200"
    >
      暂停
    </button>
    <button
      @click="reset"
      class="text-xs px-2 py-1 bg-gray-100 text-gray-600 rounded hover:bg-gray-200"
    >
      重置
    </button>
  </div>
</template>