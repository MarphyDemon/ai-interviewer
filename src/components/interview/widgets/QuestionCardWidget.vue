<script setup lang="ts">
import { renderMarkdown } from '@/utils/markdown'

defineProps<{ data: Record<string, any> }>()

const difficultyCls: Record<string, string> = {
  简单: 'bg-green-100 text-green-700',
  中等: 'bg-yellow-100 text-yellow-700',
  困难: 'bg-red-100 text-red-700',
}
</script>

<template>
  <div class="rounded-xl border border-gray-200 bg-white/95 p-4 shadow-sm backdrop-blur">
    <div class="mb-2 flex items-center gap-2">
      <p class="text-xs font-semibold text-gray-500">算法题</p>
      <span
        v-if="data.difficulty"
        class="rounded px-1.5 py-0.5 text-[10px]"
        :class="difficultyCls[data.difficulty] || 'bg-gray-100 text-gray-600'"
      >
        {{ data.difficulty }}
      </span>
    </div>

    <p class="mb-2 text-sm font-medium text-gray-800">{{ data.title }}</p>

    <div
      class="markdown-body max-h-40 overflow-y-auto text-xs leading-relaxed text-gray-600"
      v-html="renderMarkdown(String(data.description || ''))"
    />

    <div v-if="data.tags?.length" class="mt-2 flex flex-wrap gap-1">
      <span
        v-for="(t, i) in data.tags"
        :key="i"
        class="rounded bg-gray-100 px-1.5 py-0.5 text-[10px] text-gray-500"
      >
        {{ t }}
      </span>
    </div>
  </div>
</template>
