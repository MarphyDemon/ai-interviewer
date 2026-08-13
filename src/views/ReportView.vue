<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { getReport, downloadReportPdf } from '@/api/report'
import type { ReportData, MatchBreakdownItem } from '@/types'

const { t } = useI18n()
const router = useRouter()
const props = defineProps<{ id: string }>()

const report = ref<ReportData | null>(null)
const loading = ref(true)
const errorMsg = ref('')

onMounted(async () => {
  try {
    report.value = await getReport(Number(props.id))
    refreshMatch()
  } catch (e: any) {
    errorMsg.value = e.message
  } finally {
    loading.value = false
  }
})

const exporting = ref(false)

async function exportPDF() {
  exporting.value = true
  try {
    await downloadReportPdf(Number(props.id))
  } catch (e: any) {
    errorMsg.value = e.message || 'PDF 导出失败'
  } finally {
    exporting.value = false
  }
}

const hasMatch = ref(false)
function refreshMatch() {
  hasMatch.value = !!report.value && !!report.value.matchBreakdown && report.value.matchBreakdown.length > 0
}

function statusMeta(status: MatchBreakdownItem['status']) {
  switch (status) {
    case 'met':
      return { label: '满足', cls: 'bg-green-100 text-green-700' }
    case 'partial':
      return { label: '部分', cls: 'bg-amber-100 text-amber-700' }
    case 'gap':
      return { label: '不足', cls: 'bg-red-100 text-red-700' }
    default:
      return { label: status, cls: 'bg-gray-100 text-gray-600' }
  }
}
</script>

<template>
  <div class="mx-auto max-w-3xl px-4 py-10">
      <div v-if="loading" class="py-20 text-center text-gray-400">{{ t('common.loading') }}</div>
      <div v-else-if="errorMsg" class="py-20 text-center text-red-500">{{ errorMsg }}</div>

      <div v-else-if="report" class="space-y-6">
        <div class="card">
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

          <div v-if="hasMatch" class="mb-6">
            <div class="mb-3 flex items-center justify-between">
              <h3 class="font-semibold text-gray-700">人岗匹配</h3>
              <div class="text-right">
                <span class="text-xs text-gray-400">匹配度</span>
                <p class="text-3xl font-bold text-gradient">{{ report.matchScore ?? '-' }}</p>
              </div>
            </div>
            <div class="overflow-hidden rounded-xl border border-primary-100">
              <table class="w-full text-sm">
                <thead class="bg-primary-50/60 text-xs text-gray-500">
                  <tr>
                    <th class="px-3 py-2 text-left font-medium">JD 要求</th>
                    <th class="px-3 py-2 text-left font-medium">状态</th>
                    <th class="px-3 py-2 text-left font-medium">依据</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-gray-100">
                  <tr v-for="(item, idx) in report.matchBreakdown" :key="idx" class="align-top">
                    <td class="px-3 py-2 text-gray-700">{{ item.requirement }}</td>
                    <td class="px-3 py-2">
                      <span :class="['inline-block rounded-full px-2 py-0.5 text-xs font-medium', statusMeta(item.status).cls]">
                        {{ statusMeta(item.status).label }}
                      </span>
                    </td>
                    <td class="px-3 py-2 text-gray-500">{{ item.evidence }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
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

        <div class="card">
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
            :disabled="exporting"
            class="btn-primary !py-2"
          >
            {{ exporting ? t('common.loading') : t('report.exportPdf') }}
          </button>
          <button
            @click="router.push('/history')"
            class="btn-ghost !py-2"
          >
            {{ t('report.viewHistory') }}
          </button>
        </div>
      </div>
    </div>
</template>
