<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  getReport,
  downloadReportPdf,
  getSharedReport,
  getShareStatus,
  createShareLink,
  revokeShareLink,
  type ShareStatus,
} from '@/api/report'
import type { ReportData, MatchBreakdownItem } from '@/types'

const { t } = useI18n()
const router = useRouter()
const props = defineProps<{ id?: string; token?: string }>()

const shareMode = computed(() => !!props.token)

const report = ref<ReportData | null>(null)
const loading = ref(true)
const errorMsg = ref('')

// 分享相关状态（仅 report 模式使用）
const shareStatus = ref<ShareStatus | null>(null)
const shareLoading = ref(false)
const copied = ref(false)

onMounted(async () => {
  try {
    if (shareMode.value && props.token) {
      report.value = await getSharedReport(props.token)
    } else if (props.id) {
      report.value = await getReport(Number(props.id))
      // 拉取分享状态
      try {
        shareStatus.value = await getShareStatus(Number(props.id))
      } catch {
        // 忽略分享状态失败
      }
    }
    refreshMatch()
  } catch (e: any) {
    errorMsg.value = e.message || '报告加载失败'
  } finally {
    loading.value = false
  }
})

const exporting = ref(false)

async function exportPDF() {
  if (!props.id) return
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

const shareUrl = computed(() => {
  if (shareStatus.value?.token && !shareStatus.value.expired) {
    return `${window.location.origin}/share/${shareStatus.value.token}`
  }
  return ''
})

async function generateShare() {
  if (!props.id) return
  shareLoading.value = true
  try {
    const res = await createShareLink(Number(props.id))
    shareStatus.value = {
      token: res.token,
      expiresAt: res.expiresAt,
      expired: false,
    }
    await copyShareUrl()
  } catch (e: any) {
    errorMsg.value = e.message || '生成分享链接失败'
  } finally {
    shareLoading.value = false
  }
}

async function revokeShare() {
  if (!props.id) return
  if (!confirm('确认吊销分享链接？吊销后已发出的链接将立即失效。')) return
  shareLoading.value = true
  try {
    await revokeShareLink(Number(props.id))
    shareStatus.value = null
  } catch (e: any) {
    errorMsg.value = e.message || '吊销失败'
  } finally {
    shareLoading.value = false
  }
}

async function copyShareUrl() {
  if (!shareUrl.value) return
  try {
    await navigator.clipboard.writeText(shareUrl.value)
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  } catch {
    // 剪贴板权限拒绝时降级
    const ta = document.createElement('textarea')
    ta.value = shareUrl.value
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  }
}

function formatDate(iso: string | null): string {
  if (!iso) return '-'
  try {
    return new Date(iso).toLocaleString('zh-CN')
  } catch {
    return iso
  }
}
</script>

<template>
  <div class="mx-auto max-w-3xl px-4 py-10">
      <div v-if="loading" class="py-20 text-center text-gray-400">{{ t('common.loading') }}</div>
      <div v-else-if="errorMsg" class="py-20 text-center text-red-500">{{ errorMsg }}</div>

      <div v-else-if="report" class="space-y-6">
        <!-- 分享模式标识 -->
        <div v-if="shareMode" class="rounded-lg border border-primary-100 bg-primary-50/50 px-4 py-2 text-sm text-primary-700">
          🔗 您正在查看分享的面试报告
        </div>

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

        <!-- 操作按钮（分享模式隐藏） -->
        <div v-if="!shareMode" class="space-y-4">
          <!-- 分享链接区 -->
          <div class="card">
            <div class="mb-3 flex items-center justify-between">
              <h3 class="font-semibold text-gray-700">分享报告</h3>
              <span v-if="shareStatus?.token && !shareStatus.expired" class="text-xs text-gray-400">
                过期时间：{{ formatDate(shareStatus.expiresAt) }}
              </span>
            </div>

            <div v-if="shareStatus?.token && !shareStatus.expired" class="space-y-2">
              <div class="flex items-center gap-2">
                <input
                  :value="shareUrl"
                  readonly
                  class="flex-1 rounded-lg border border-gray-300 bg-gray-50 px-3 py-2 text-sm text-gray-600"
                  @click="($event.target as HTMLInputElement).select()"
                />
                <button
                  @click="copyShareUrl"
                  class="rounded-lg bg-primary-50 px-3 py-2 text-sm font-medium text-primary-700 transition hover:bg-primary-100"
                >
                  {{ copied ? '✓ 已复制' : '复制' }}
                </button>
                <button
                  @click="revokeShare"
                  :disabled="shareLoading"
                  class="rounded-lg bg-red-50 px-3 py-2 text-sm font-medium text-red-600 transition hover:bg-red-100 disabled:opacity-50"
                >
                  吊销
                </button>
              </div>
              <p class="text-xs text-gray-400">链接 7 天内有效，可随时吊销</p>
            </div>

            <div v-else-if="shareStatus?.expired" class="space-y-2">
              <p class="text-sm text-amber-600">分享链接已过期</p>
              <button
                @click="generateShare"
                :disabled="shareLoading"
                class="btn-primary !py-2"
              >
                {{ shareLoading ? '生成中...' : '重新生成分享链接' }}
              </button>
            </div>

            <button
              v-else
              @click="generateShare"
              :disabled="shareLoading"
              class="btn-primary !py-2"
            >
              {{ shareLoading ? '生成中...' : '生成分享链接' }}
            </button>
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
    </div>
</template>
