<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useResumeStore } from '@/stores/resume'
import { useInterviewStore } from '@/stores/interview'
import LangToggle from '@/components/common/LangToggle.vue'
import type { Difficulty, InterviewerStyle } from '@/types'

const { t } = useI18n()
const router = useRouter()
const resumeStore = useResumeStore()
const interviewStore = useInterviewStore()

const position = ref('frontend')
const difficulty = ref<Difficulty>('mid')
const duration = ref(30)
const style = ref<InterviewerStyle>('friendly')
const selectedResumeId = ref<number | undefined>(undefined)
const starting = ref(false)

const positions = ['frontend', 'backend', 'algorithm', 'product'] as const
const difficulties: Difficulty[] = ['junior', 'mid', 'senior']
const durations = [15, 30, 45]
const styles: InterviewerStyle[] = ['strict', 'friendly', 'pressure']

async function start() {
  starting.value = true
  try {
    await interviewStore.start({
      position: position.value,
      difficulty: difficulty.value,
      duration: duration.value,
      style: style.value,
      resumeId: selectedResumeId.value,
    })
    router.push('/interview')
  } catch (e: any) {
    alert(e.message)
  } finally {
    starting.value = false
  }
}
</script>

<template>
  <div class="min-h-screen bg-gray-50">
    <div class="mx-auto max-w-2xl px-4 py-8">
      <div class="mb-6 flex items-center justify-between">
        <button @click="router.back()" class="text-sm text-gray-500 hover:text-gray-700">
          ← {{ t('common.back') }}
        </button>
        <LangToggle />
      </div>
      <h1 class="mb-8 text-2xl font-bold text-gray-800">{{ t('setup.title') }}</h1>

      <div class="space-y-6 rounded-lg bg-white p-6 shadow-sm">
        <div>
          <label class="mb-2 block text-sm font-medium text-gray-700">{{ t('setup.position') }}</label>
          <div class="flex flex-wrap gap-2">
            <button
              v-for="p in positions"
              :key="p"
              @click="position = p"
              :class="[
                'rounded-lg px-4 py-2 text-sm font-medium transition',
                position === p
                  ? 'bg-primary-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200',
              ]"
            >
              {{ t('positions.' + p) }}
            </button>
          </div>
        </div>

        <div>
          <label class="mb-2 block text-sm font-medium text-gray-700">{{ t('setup.difficulty') }}</label>
          <div class="flex gap-2">
            <button
              v-for="d in difficulties"
              :key="d"
              @click="difficulty = d"
              :class="[
                'rounded-lg px-4 py-2 text-sm font-medium transition',
                difficulty === d
                  ? 'bg-primary-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200',
              ]"
            >
              {{ t('difficulty.' + d) }}
            </button>
          </div>
        </div>

        <div>
          <label class="mb-2 block text-sm font-medium text-gray-700">{{ t('setup.duration') }}</label>
          <div class="flex gap-2">
            <button
              v-for="d in durations"
              :key="d"
              @click="duration = d"
              :class="[
                'rounded-lg px-4 py-2 text-sm font-medium transition',
                duration === d
                  ? 'bg-primary-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200',
              ]"
            >
              {{ d }}
            </button>
          </div>
        </div>

        <div>
          <label class="mb-2 block text-sm font-medium text-gray-700">{{ t('setup.interviewerStyle') }}</label>
          <div class="flex gap-2">
            <button
              v-for="s in styles"
              :key="s"
              @click="style = s"
              :class="[
                'rounded-lg px-4 py-2 text-sm font-medium transition',
                style === s
                  ? 'bg-primary-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200',
              ]"
            >
              {{ t('styles.' + s) }}
            </button>
          </div>
        </div>

        <div>
          <label class="mb-2 block text-sm font-medium text-gray-700">{{ t('setup.resume') }}</label>
          <select
            v-model="selectedResumeId"
            class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
          >
            <option :value="undefined">{{ t('setup.noResume') }}</option>
            <option
              v-for="resume in resumeStore.resumes"
              :key="resume.id"
              :value="resume.id"
            >
              {{ resume.filename }}
            </option>
          </select>
        </div>

        <button
          @click="start"
          :disabled="starting"
          class="w-full rounded-lg bg-primary-600 px-6 py-3 text-white font-medium hover:bg-primary-700 transition disabled:opacity-50"
        >
          {{ starting ? t('setup.starting') : t('setup.start') }}
        </button>
      </div>
    </div>
  </div>
</template>
