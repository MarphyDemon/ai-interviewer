<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { getRecordings, type RecordingItem } from '@/api/recordings'
import * as interviewApi from '@/api/interview'

const { t } = useI18n()
const route = useRoute()
const interviewId = Number(route.params.interviewId)

const recordings = ref<RecordingItem[]>([])
const loading = ref(true)
const interview = ref<any>(null)
const currentAudio = ref<string | null>(null)
const audioRef = ref<HTMLAudioElement | null>(null)

onMounted(async () => {
  try {
    const [recs, intv] = await Promise.all([
      getRecordings(interviewId),
      interviewApi.getInterview(interviewId),
    ])
    recordings.value = recs
    interview.value = intv
  } catch (e: any) {
    console.error('加载回放数据失败', e)
  } finally {
    loading.value = false
  }
})

function playRecording(url: string) {
  currentAudio.value = url
  if (audioRef.value) {
    audioRef.value.src = url
    audioRef.value.play()
  }
}

function formatDuration(ms: number) {
  const s = Math.floor(ms / 1000)
  const m = Math.floor(s / 60)
  const sec = s % 60
  return `${m}:${sec.toString().padStart(2, '0')}`
}

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes}B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`
}
</script>

<template>
  <div class="mx-auto max-w-4xl px-4 py-8">
    <!-- 页头 -->
    <div class="mb-6">
      <h1 class="text-2xl font-bold text-gray-900">面试回放</h1>
      <p v-if="interview" class="mt-1 text-sm text-gray-500">
        {{ interview.position }} · {{ interview.difficulty }} · {{ interview.status }}
      </p>
    </div>

    <div v-if="loading" class="py-20 text-center text-gray-400">
      {{ t('common.loading') }}
    </div>

    <div v-else-if="recordings.length === 0" class="rounded-xl border-2 border-dashed border-gray-200 py-20 text-center text-gray-400">
      <p class="text-lg">暂无录制文件</p>
      <p class="mt-2 text-sm">面试时点击「录制」按钮即可录制音频</p>
    </div>

    <div v-else class="space-y-4">
      <!-- 音频播放器 -->
      <div v-if="currentAudio" class="card !p-4">
        <audio ref="audioRef" :src="currentAudio" controls class="w-full" />
      </div>

      <!-- 录制文件列表 -->
      <div class="card !p-0">
        <div class="border-b border-gray-100 px-5 py-3">
          <h2 class="text-sm font-semibold text-gray-700">录制片段（{{ recordings.length }}）</h2>
        </div>
        <div class="divide-y divide-gray-50">
          <div
            v-for="(rec, i) in recordings"
            :key="rec.id"
            @click="playRecording(rec.url)"
            class="flex cursor-pointer items-center justify-between px-5 py-3 transition hover:bg-gray-50"
          >
            <div class="flex items-center gap-3">
              <span class="flex h-8 w-8 items-center justify-center rounded-full bg-primary-50 text-xs text-primary-600">
                {{ i + 1 }}
              </span>
              <div>
                <div class="text-sm font-medium text-gray-800">
                  {{ rec.streamType === 'audio' ? '音频' : '视频' }}片段
                </div>
                <div class="text-xs text-gray-400">
                  {{ formatSize(rec.fileSize) }}
                  <span v-if="rec.durationMs"> · {{ formatDuration(rec.durationMs) }}</span>
                  · {{ rec.mimeType }}
                </div>
              </div>
            </div>
            <div class="text-xs text-gray-400">
              {{ rec.createdAt ? new Date(rec.createdAt).toLocaleString() : '' }}
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>