<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ data: Record<string, any> }>()

const score = computed<number | null>(() =>
  typeof props.data.score === 'number' ? props.data.score : null,
)
const strengths = computed<string[]>(() => props.data.strengths ?? [])
const gaps = computed<string[]>(() => props.data.gaps ?? [])
</script>

<template>
  <div class="rounded-xl border border-gray-200 bg-white/95 p-3 shadow-sm backdrop-blur">
    <div class="mb-1 flex items-center gap-2">
      <p class="text-xs font-semibold text-gray-500">即时评分</p>
      <span v-if="score !== null" class="text-sm font-bold text-primary-700">{{ score }}</span>
    </div>

    <p v-if="data.verdict" class="text-xs leading-relaxed text-gray-700">{{ data.verdict }}</p>

    <p v-if="strengths.length" class="mt-1.5 text-[11px] leading-relaxed text-green-700">
      + {{ strengths.join('；') }}
    </p>
    <p v-if="gaps.length" class="mt-0.5 text-[11px] leading-relaxed text-amber-700">
      - {{ gaps.join('；') }}
    </p>
  </div>
</template>
