<script setup lang="ts">
import { computed } from 'vue'
import type { MatchBreakdownItemLite } from '@/types'

const props = defineProps<{ data: Record<string, any> }>()

const breakdown = computed<MatchBreakdownItemLite[]>(
  () => (props.data.matchBreakdown ?? []) as MatchBreakdownItemLite[],
)

const score = computed<number | null>(() =>
  typeof props.data.matchScore === 'number' ? props.data.matchScore : null,
)

const statusMeta: Record<string, { label: string; cls: string }> = {
  met: { label: '满足', cls: 'bg-green-100 text-green-700' },
  partial: { label: '部分', cls: 'bg-amber-100 text-amber-700' },
  gap: { label: '不足', cls: 'bg-red-100 text-red-700' },
}
</script>

<template>
  <div class="rounded-xl border border-gray-200 bg-white/95 p-4 shadow-sm backdrop-blur">
    <p class="mb-2 text-xs font-semibold text-gray-500">人岗匹配</p>

    <div v-if="score !== null" class="mb-3">
      <div class="mb-1 flex items-baseline gap-1">
        <span class="text-2xl font-bold text-primary-700">{{ score }}</span>
        <span class="text-xs text-gray-400">/ 100</span>
      </div>
      <div class="h-1.5 w-full overflow-hidden rounded-full bg-gray-100">
        <div
          class="h-full rounded-full bg-primary-500 transition-all"
          :style="{ width: `${Math.max(0, Math.min(100, score))}%` }"
        />
      </div>
    </div>

    <div v-if="breakdown.length" class="mb-2 space-y-1.5">
      <div v-for="(item, i) in breakdown" :key="i" class="flex items-start gap-2">
        <span
          class="mt-0.5 shrink-0 rounded px-1.5 py-0.5 text-[10px]"
          :class="(statusMeta[item.status] || statusMeta.partial).cls"
        >
          {{ (statusMeta[item.status] || statusMeta.partial).label }}
        </span>
        <div class="min-w-0">
          <p class="text-xs text-gray-700">{{ item.requirement }}</p>
          <p v-if="item.evidence" class="text-[11px] leading-relaxed text-gray-400">{{ item.evidence }}</p>
        </div>
      </div>
    </div>

    <p v-if="data.jobFit" class="border-t border-gray-100 pt-2 text-xs leading-relaxed text-gray-600">
      {{ data.jobFit }}
    </p>
  </div>
</template>
