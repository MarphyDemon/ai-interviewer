<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import * as metricsApi from '@/api/metrics'
import type { InterviewMetricRow, MetricsSummary, MetricStats } from '@/types'

/**
 * 实测指标页：展示具身链路的真实实测值（首字延迟 / 工具耗时 / 端到端 / 打断延迟）。
 *
 * 数据来自服务端自动埋点（brain 流式产出时落库）+ 客户端上报（打断耗时），
 * 对应赛题要求的"公开实测值"，而不是估算或行业平均值。
 */

const { t, locale } = useI18n()
const router = useRouter()

const KIND_KEYS = ['ttfa', 'tool', 'e2e', 'interrupt'] as const

const STAGE_LABELS: Record<string, { zh: string; en: string }> = {
  opening: { zh: '开场', en: 'Opening' },
  ask: { zh: '提问', en: 'Question' },
  followup: { zh: '追问', en: 'Follow-up' },
  algorithm: { zh: '算法题', en: 'Coding' },
  judge: { zh: '判题', en: 'Review' },
  closing: { zh: '收尾', en: 'Closing' },
  report: { zh: '报告', en: 'Report' },
  finished: { zh: '已结束', en: 'Finished' },
}

const days = ref(30)
const loading = ref(false)
const errorMsg = ref('')
const summary = ref<MetricsSummary | null>(null)
const rows = ref<InterviewMetricRow[]>([])

const cards = computed(() =>
  KIND_KEYS.map((key) => ({
    key,
    label: t(`metrics.${key}`),
    stats: summary.value?.kinds?.[key] as MetricStats | undefined,
  })),
)

const hasData = computed(() => (summary.value?.metricCount ?? 0) > 0)

function fmtMs(value?: number | null) {
  return value === null || value === undefined ? '—' : `${value} ms`
}

function stageLabel(stage: string) {
  const entry = STAGE_LABELS[stage]
  if (!entry) return stage || '—'
  return locale.value === 'zh' ? entry.zh : entry.en
}

function fmtDate(iso: string | null) {
  if (!iso) return '—'
  return iso.replace('T', ' ').slice(0, 16)
}

async function load() {
  loading.value = true
  errorMsg.value = ''
  try {
    const [s, list] = await Promise.all([
      metricsApi.getMetricsSummary(days.value),
      metricsApi.getInterviewMetrics(50),
    ])
    summary.value = s
    rows.value = list
  } catch (e: any) {
    errorMsg.value = `${t('metrics.loadFailed')}${e?.message ?? e}`
  } finally {
    loading.value = false
  }
}

/** 导出 CSV（带 BOM，Excel 直接可读） */
function exportCsv() {
  const header = [
    'interviewId',
    'position',
    'difficulty',
    'stage',
    'startedAt',
    'ttfaMs',
    'toolMs',
    'e2eMs',
    'interruptMs',
    'toolCalls',
  ]
  const lines = rows.value.map((r) =>
    [
      r.interviewId,
      r.position,
      r.difficulty,
      r.stage,
      r.startedAt ?? '',
      r.ttfaMs ?? '',
      r.toolMs ?? '',
      r.e2eMs ?? '',
      r.interruptMs ?? '',
      r.toolCalls,
    ].join(','),
  )
  const csv = `\uFEFF${[header.join(','), ...lines].join('\n')}`
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }))
  const a = document.createElement('a')
  a.href = url
  a.download = `interview-metrics-${days.value}d.csv`
  a.click()
  URL.revokeObjectURL(url)
}

onMounted(load)
</script>

<template>
  <div class="mx-auto max-w-5xl px-4 py-6">
    <div class="mb-4 flex flex-wrap items-center justify-between gap-3">
      <div>
        <h1 class="text-lg font-bold text-gray-900">{{ t('metrics.title') }}</h1>
        <p class="mt-0.5 text-xs text-gray-500">{{ t('metrics.subtitle') }}</p>
      </div>

      <div class="flex items-center gap-2">
        <select
          v-model.number="days"
          class="rounded-lg border border-gray-200 bg-white px-2 py-1.5 text-xs text-gray-700"
          @change="load"
        >
          <option :value="7">{{ t('metrics.days7') }}</option>
          <option :value="30">{{ t('metrics.days30') }}</option>
          <option :value="90">{{ t('metrics.days90') }}</option>
        </select>
        <button
          class="rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 transition hover:bg-gray-50 disabled:opacity-50"
          :disabled="!rows.length"
          @click="exportCsv"
        >
          {{ t('metrics.exportCsv') }}
        </button>
      </div>
    </div>

    <p v-if="errorMsg" class="mb-3 rounded-lg bg-red-50 px-3 py-2 text-xs text-red-600">
      {{ errorMsg }}
    </p>

    <div v-if="loading" class="grid grid-cols-2 gap-3 md:grid-cols-4">
      <div v-for="i in 4" :key="i" class="h-24 animate-pulse rounded-xl bg-gray-100" />
    </div>

    <template v-else>
      <!-- 聚合卡片：均值 / P50 / P95 -->
      <div class="grid grid-cols-2 gap-3 md:grid-cols-4">
        <div
          v-for="card in cards"
          :key="card.key"
          class="rounded-xl border border-gray-200 bg-white p-3"
        >
          <p class="text-xs font-semibold text-gray-500">{{ card.label }}</p>
          <p class="mt-1 text-xl font-bold text-gray-900">
            {{ fmtMs(card.stats?.avg) }}
          </p>
          <p class="mt-1 text-[11px] leading-relaxed text-gray-400">
            {{ t('metrics.p50') }} {{ fmtMs(card.stats?.p50) }} ·
            {{ t('metrics.p95') }} {{ fmtMs(card.stats?.p95) }} ·
            {{ t('metrics.count') }} {{ card.stats?.count ?? 0 }}
          </p>
        </div>
      </div>

      <p
        v-if="!hasData"
        class="mt-4 rounded-xl border border-dashed border-gray-200 px-3 py-8 text-center text-xs text-gray-400"
      >
        {{ t('metrics.noData') }}
      </p>

      <!-- 工具耗时排行 -->
      <div v-if="summary?.toolTop?.length" class="mt-6">
        <h2 class="mb-2 text-sm font-semibold text-gray-800">{{ t('metrics.toolRanking') }}</h2>
        <div class="overflow-hidden rounded-xl border border-gray-200 bg-white">
          <table class="w-full text-left text-xs">
            <thead class="bg-gray-50 text-gray-500">
              <tr>
                <th class="px-3 py-2 font-medium">{{ t('metrics.toolName') }}</th>
                <th class="px-3 py-2 font-medium">{{ t('metrics.calls') }}</th>
                <th class="px-3 py-2 font-medium">{{ t('metrics.avg') }}</th>
                <th class="px-3 py-2 font-medium">{{ t('metrics.p95') }}</th>
                <th class="px-3 py-2 font-medium">{{ t('metrics.max') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="tool in summary.toolTop"
                :key="tool.name"
                class="border-t border-gray-100 text-gray-700"
              >
                <td class="px-3 py-2 font-mono">{{ tool.name }}</td>
                <td class="px-3 py-2">{{ tool.count }}</td>
                <td class="px-3 py-2">{{ fmtMs(tool.avg) }}</td>
                <td class="px-3 py-2">{{ fmtMs(tool.p95) }}</td>
                <td class="px-3 py-2">{{ fmtMs(tool.max) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- 每次面试明细 -->
      <div v-if="rows.length" class="mt-6">
        <h2 class="mb-2 text-sm font-semibold text-gray-800">{{ t('metrics.perInterview') }}</h2>
        <div class="overflow-x-auto rounded-xl border border-gray-200 bg-white">
          <table class="w-full min-w-[720px] text-left text-xs">
            <thead class="bg-gray-50 text-gray-500">
              <tr>
                <th class="px-3 py-2 font-medium">{{ t('metrics.interviewId') }}</th>
                <th class="px-3 py-2 font-medium">{{ t('metrics.position') }}</th>
                <th class="px-3 py-2 font-medium">{{ t('metrics.startedAt') }}</th>
                <th class="px-3 py-2 font-medium">{{ t('metrics.stage') }}</th>
                <th class="px-3 py-2 font-medium">{{ t('metrics.ttfa') }}</th>
                <th class="px-3 py-2 font-medium">{{ t('metrics.tool') }}</th>
                <th class="px-3 py-2 font-medium">{{ t('metrics.e2e') }}</th>
                <th class="px-3 py-2 font-medium">{{ t('metrics.interrupt') }}</th>
                <th class="px-3 py-2 font-medium">{{ t('metrics.toolCalls') }}</th>
                <th class="px-3 py-2 font-medium"></th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in rows"
                :key="row.interviewId"
                class="border-t border-gray-100 text-gray-700"
              >
                <td class="px-3 py-2">#{{ row.interviewId }}</td>
                <td class="px-3 py-2">
                  {{ row.position }}
                  <span class="text-gray-400">/ {{ row.difficulty }}</span>
                </td>
                <td class="px-3 py-2 text-gray-400">{{ fmtDate(row.startedAt) }}</td>
                <td class="px-3 py-2">{{ stageLabel(row.stage) }}</td>
                <td class="px-3 py-2">{{ fmtMs(row.ttfaMs) }}</td>
                <td class="px-3 py-2">{{ fmtMs(row.toolMs) }}</td>
                <td class="px-3 py-2">{{ fmtMs(row.e2eMs) }}</td>
                <td class="px-3 py-2">{{ fmtMs(row.interruptMs) }}</td>
                <td class="px-3 py-2">{{ row.toolCalls }}</td>
                <td class="px-3 py-2 text-right">
                  <button
                    class="text-primary-600 transition hover:underline"
                    @click="router.push(`/report/${row.interviewId}`)"
                  >
                    {{ t('metrics.viewReport') }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>
