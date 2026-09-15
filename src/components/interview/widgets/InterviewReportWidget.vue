<script setup lang="ts">
import { useRouter } from 'vue-router'

const props = defineProps<{ data: Record<string, any> }>()

const router = useRouter()

function openReport() {
  if (props.data.interviewId) {
    router.push(`/report/${props.data.interviewId}`)
  }
}
</script>

<template>
  <div class="rounded-xl border border-primary-200 bg-white/95 p-4 shadow-sm backdrop-blur">
    <p class="mb-2 text-xs font-semibold text-gray-500">面试报告</p>

    <div class="mb-3 flex items-baseline gap-1">
      <span class="text-2xl font-bold text-primary-700">{{ data.totalScore ?? '-' }}</span>
      <span class="text-xs text-gray-400">总分</span>
    </div>

    <p v-if="data.summary" class="mb-3 text-xs leading-relaxed text-gray-600">{{ data.summary }}</p>

    <div v-if="data.dimensionScores?.length" class="mb-3 space-y-1.5">
      <div v-for="(d, i) in data.dimensionScores" :key="i">
        <div class="mb-0.5 flex justify-between text-[11px] text-gray-500">
          <span>{{ d.label }}</span>
          <span>{{ d.score }}</span>
        </div>
        <div class="h-1 w-full overflow-hidden rounded-full bg-gray-100">
          <div
            class="h-full rounded-full bg-primary-400"
            :style="{ width: `${Math.max(0, Math.min(100, Number(d.score) || 0))}%` }"
          />
        </div>
      </div>
    </div>

    <p v-if="data.jobFit" class="mb-3 border-t border-gray-100 pt-2 text-xs leading-relaxed text-gray-600">
      {{ data.jobFit }}
    </p>

    <button
      v-if="data.interviewId"
      class="w-full rounded-lg bg-primary-600 px-3 py-2 text-xs text-white transition hover:bg-primary-700"
      @click="openReport"
    >
      查看完整报告
    </button>
  </div>
</template>
