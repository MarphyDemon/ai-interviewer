<script setup lang="ts">
import { computed, ref } from 'vue'
import type { JudgeCaseLite } from '@/types'

const props = defineProps<{ data: Record<string, any> }>()

const expanded = ref(false)

const passed = computed(() => props.data.status === 'accepted')
const cases = computed<JudgeCaseLite[]>(() => (props.data.cases ?? []) as JudgeCaseLite[])
const shownCases = computed(() => (expanded.value ? cases.value : cases.value.slice(0, 3)))
</script>

<template>
  <div class="rounded-xl border border-gray-200 bg-white/95 p-4 shadow-sm backdrop-blur">
    <div class="mb-2 flex items-center justify-between">
      <p class="truncate text-xs font-semibold text-gray-500">判题结果 · {{ data.title || '' }}</p>
      <span
        class="shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium"
        :class="passed ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'"
      >
        {{ passed ? '通过' : data.status }}
      </span>
    </div>

    <div class="mb-2 flex gap-3 text-xs text-gray-500">
      <span>用例 {{ data.passCount }}/{{ data.totalCount }}</span>
      <span v-if="data.durationMs">耗时 {{ data.durationMs }}ms</span>
    </div>

    <pre
      v-if="data.compileError"
      class="mb-2 max-h-24 overflow-auto rounded bg-red-50 p-2 text-[11px] leading-relaxed text-red-700"
    >{{ data.compileError }}</pre>

    <div v-if="shownCases.length" class="space-y-1.5">
      <div
        v-for="(c, i) in shownCases"
        :key="i"
        class="rounded border p-2 text-[11px] leading-relaxed"
        :class="c.passed ? 'border-green-100 bg-green-50/60' : 'border-red-100 bg-red-50/60'"
      >
        <p :class="c.passed ? 'text-green-700' : 'text-red-700'" class="font-medium">
          用例 {{ i + 1 }} · {{ c.passed ? '通过' : '未通过' }}
        </p>
        <p class="mt-0.5 text-gray-500">输入：<span class="text-gray-700">{{ c.input || '(空)' }}</span></p>
        <p class="text-gray-500">期望：<span class="text-gray-700">{{ c.expected }}</span></p>
        <p v-if="!c.passed" class="text-gray-500">实际：<span class="text-gray-700">{{ c.actual || '(空)' }}</span></p>
      </div>
    </div>

    <button
      v-if="cases.length > 3"
      class="mt-2 text-[11px] text-primary-600 hover:text-primary-700"
      @click="expanded = !expanded"
    >
      {{ expanded ? '收起' : `展开全部 ${cases.length} 个用例` }}
    </button>
  </div>
</template>
