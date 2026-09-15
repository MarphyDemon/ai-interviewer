<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ data: Record<string, any> }>()

const highlights = computed<string[]>(() => props.data.highlights ?? [])
const weaknesses = computed<string[]>(() => props.data.weaknesses ?? [])
</script>

<template>
  <div class="rounded-xl border border-gray-200 bg-white/95 p-4 shadow-sm backdrop-blur">
    <p class="mb-2 text-xs font-semibold text-gray-500">简历要点</p>
    <p v-if="data.filename" class="mb-2 truncate text-xs text-gray-400">{{ data.filename }}</p>

    <div class="mb-3 flex gap-2">
      <div class="flex-1 rounded-lg bg-primary-50 px-2 py-1.5 text-center">
        <p class="text-[10px] text-primary-600">结构完整度</p>
        <p class="text-base font-semibold text-primary-700">{{ data.structureScore ?? '-' }}</p>
      </div>
      <div class="flex-1 rounded-lg bg-primary-50 px-2 py-1.5 text-center">
        <p class="text-[10px] text-primary-600">岗位匹配</p>
        <p class="text-base font-semibold text-primary-700">{{ data.positionMatch ?? '-' }}</p>
      </div>
    </div>

    <div v-if="highlights.length" class="mb-2">
      <p class="mb-1 text-xs font-medium text-green-700">亮点</p>
      <ul class="space-y-0.5">
        <li v-for="(h, i) in highlights" :key="i" class="text-xs leading-relaxed text-gray-600">· {{ h }}</li>
      </ul>
    </div>

    <div v-if="weaknesses.length">
      <p class="mb-1 text-xs font-medium text-amber-700">待确认</p>
      <ul class="space-y-0.5">
        <li v-for="(w, i) in weaknesses" :key="i" class="text-xs leading-relaxed text-gray-600">· {{ w }}</li>
      </ul>
    </div>
  </div>
</template>
