<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { getSharedReport } from '@/api/share'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
const route = useRoute()
const token = route.params.token as string

const loading = ref(true)
const data = ref<any>(null)
const error = ref('')

onMounted(async () => {
  try {
    data.value = await getSharedReport(token)
  } catch (e: any) {
    error.value = e.message || '加载失败'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="mx-auto max-w-4xl px-4 py-8">
    <!-- 页头 -->
    <div class="mb-6">
      <h1 class="text-2xl font-bold text-gray-900">{{ t('share.title') }}</h1>
      <p v-if="data" class="mt-1 text-sm text-gray-500">
        {{ data.position }} · {{ data.difficulty }}
      </p>
    </div>

    <div v-if="loading" class="py-20 text-center text-gray-400">
      {{ t('common.loading') }}
    </div>

    <div v-else-if="error" class="card !p-8 text-center">
      <p class="text-lg font-medium text-red-600">{{ error }}</p>
      <p class="mt-2 text-sm text-gray-400">{{ t('share.invalidOrExpired') }}</p>
    </div>

    <div v-else class="space-y-6">
      <!-- 评分卡片 -->
      <div class="card !p-6">
        <h2 class="mb-4 text-lg font-semibold text-gray-800">{{ t('report.overallScore') }}</h2>
        <div class="flex items-center justify-center">
          <div
            class="flex h-32 w-32 flex-col items-center justify-center rounded-full"
            :class="data.score >= 70 ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'"
          >
            <span class="text-4xl font-bold">{{ data.score }}</span>
            <span class="text-xs">/ 100</span>
          </div>
        </div>
      </div>

      <!-- 问题与回答 -->
      <div class="card !p-0">
        <div class="border-b border-gray-100 px-6 py-3">
          <h2 class="text-sm font-semibold text-gray-700">{{ t('report.questions') }}</h2>
        </div>
        <div class="divide-y divide-gray-50">
          <div v-for="(item, idx) in data.questions" :key="idx" class="px-6 py-4">
            <div class="mb-2 flex items-center justify-between">
              <span class="text-sm font-medium text-gray-800">Q{{ idx + 1 }}. {{ item.question }}</span>
              <span
                class="rounded-full px-2 py-0.5 text-xs"
                :class="item.score >= 3 ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'"
              >
                {{ item.score }}/5
              </span>
            </div>
            <p class="whitespace-pre-wrap text-sm text-gray-600">{{ item.answer }}</p>
            <p v-if="item.feedback" class="mt-1 text-xs text-gray-400">💡 {{ item.feedback }}</p>
          </div>
        </div>
      </div>

      <!-- 建议 -->
      <div class="card !p-6">
        <h2 class="mb-3 text-lg font-semibold text-gray-800">{{ t('report.suggestions') }}</h2>
        <p class="whitespace-pre-wrap text-sm text-gray-600">{{ data.suggestions }}</p>
      </div>

      <!-- 总结 -->
      <div class="card !p-6">
        <h2 class="mb-3 text-lg font-semibold text-gray-800">{{ t('report.summary') }}</h2>
        <p class="whitespace-pre-wrap text-sm text-gray-600">{{ data.summary }}</p>
      </div>
    </div>
  </div>
</template>