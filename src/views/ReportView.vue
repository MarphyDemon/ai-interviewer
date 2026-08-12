<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { getReport } from '@/api/report'
import LangToggle from '@/components/common/LangToggle.vue'
import type { ReportData } from '@/types'

const { t } = useI18n()
const router = useRouter()
const props = defineProps<{ id: string }>()

const report = ref<ReportData | null>(null)
const loading = ref(true)
const errorMsg = ref('')

onMounted(async () => {
  try {
    report.value = await getReport(Number(props.id))
  } catch (e: any) {
    errorMsg.value = e.message
  } finally {
    loading.value = false
  }
})

function exportPDF() {
  window.print()
}
</script>

<template>
  <div class="min-h-screen bg-gray-50">
    <div class="mx-auto max-w-3xl px-4 py-8">
      <div class="mb-6 flex items-center justify-between">
        <button @click="router.push('/')" class="text-sm text-gray-500 hover:text-gray-700">
          ← {{ t('common.back') }}
        </button>
        <LangToggle />
      </div>

      <div v-if="loading" class="py-20 text-center text-gray-400">{{ t('common.loading') }}</div>
      <div v-else-if="errorMsg" class="py-20 text-center text-red-500">{{ errorMsg }}</div>

      <div v-else-if="report" class="space-y-6">
        <div class="rounded-lg bg-white p-6 shadow-sm">
          <h1 class="mb-4 text-2xl font-bold text-gray-800">{{ t('report.title') }}</h1>
          <div class="mb-6 flex items-center justify-around">
            <div class="text-center">
              <p class="text-sm text-gray-400">{{ t('report.totalScore') }}</p>
              <p class="text-4xl font-bold text-primary-600">{{ report.totalScore }}</p>
            </div>
          </div>

          <div class="mb-6">
            <h3 class="mb-3 font-semibold text-gray-700">{{ t('report.dimensions') }}</h3>
            <div class="space-y-2">
              <div v-for="dim in report.dimensionScores" :key="dim.label">
                <div class="mb-1 flex justify-between text-sm">
                  <span class="text-gray-600">{{ dim.label }}</span>
                  <span class="font-medium text-gray-800">{{ dim.score }}</span>
                </div>
                <div class="h-2 rounded-full bg-gray-200">
                  <div
                    class="h-2 rounded-full bg-primary-500"
                    :style="{ width: dim.score + '%' }"
                  ></div>
                </div>
              </div>
            </div>
          </div>

          <div class="mb-6">
            <h3 class="mb-2 font-semibold text-gray-700">{{ t('report.summary') }}</h3>
            <p class="text-sm leading-relaxed text-gray-600">{{ report.summary }}</p>
          </div>

          <div v-if="report.jobFit" class="mb-6">
            <h3 class="mb-2 font-semibold text-gray-700">{{ t('report.jobFit') }}</h3>
            <p class="text-sm leading-relaxed text-gray-600">{{ report.jobFit }}</p>
          </div>

          <div v-if="report.resumeReview" class="mb-6">
            <h3 class="mb-2 font-semibold text-gray-700">{{ t('report.resumeReview') }}</h3>
            <div class="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span class="text-gray-500">{{ t('report.structureScore') }}:</span>
                <span class="ml-2 font-medium">{{ report.resumeReview.structureScore }}</span>
              </div>
              <div>
                <span class="text-gray-500">{{ t('report.positionMatch') }}:</span>
                <span class="ml-2 font-medium">{{ report.resumeReview.positionMatch }}%</span>
              </div>
            </div>
          </div>
        </div>

        <div class="rounded-lg bg-white p-6 shadow-sm">
          <h2 class="mb-4 text-xl font-semibold text-gray-800">{{ t('report.perQuestion') }}</h2>
          <div class="space-y-4">
            <div
              v-for="(review, idx) in report.perQuestionReviews"
              :key="idx"
              class="border-l-4 border-primary-200 pl-4"
            >
              <p class="mb-1 font-medium text-gray-800">Q{{ idx + 1 }}: {{ review.question }}</p>
              <p class="mb-1 text-sm text-gray-500">{{ t('report.yourAnswer') }}: {{ review.answer }}</p>
              <p class="mb-1 text-sm text-gray-600">{{ t('report.review') }}: {{ review.review }}</p>
              <p class="text-sm text-green-600">{{ t('report.referenceAnswer') }}: {{ review.referenceAnswer }}</p>
              <p class="mt-1 text-xs text-gray-400">{{ t('report.score') }}: {{ review.score }}</p>
            </div>
          </div>
        </div>

        <div class="flex gap-4">
          <button
            @click="exportPDF"
            class="rounded-lg bg-primary-600 px-6 py-2 text-white font-medium hover:bg-primary-700"
          >
            {{ t('report.exportPdf') }}
          </button>
          <button
            @click="router.push('/history')"
            class="rounded-lg border border-gray-300 px-6 py-2 text-gray-700 font-medium hover:bg-gray-100"
          >
            {{ t('report.viewHistory') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
