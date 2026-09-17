<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { InterviewChoice } from '@/types'
import { useInterviewEvents } from '@/composables/useInterviewEvents'
import { useInterviewStore } from '@/stores/interview'

/**
 * 交互控件（Picker）：候选人点选后由后端 /command 端点直接执行，
 * 不经过 LLM 解析 —— 换题 / 看提示 / 进入算法题 / 结束面试 都是确定性动作。
 */
const props = defineProps<{ data: Record<string, any> }>()

const { removeWidgetsOfType } = useInterviewEvents()
const store = useInterviewStore()
const { t } = useI18n()

const title = computed<string>(() => props.data.title || t('interview.choicesTitle'))
const options = computed<InterviewChoice[]>(() =>
  Array.isArray(props.data.options) ? props.data.options : [],
)
const busy = computed(() => store.state === 'analyzing')

async function pick(option: InterviewChoice) {
  if (busy.value) return
  removeWidgetsOfType('picker')
  await store.selectChoice(option)
}
</script>

<template>
  <div class="rounded-xl border border-primary-200 bg-white/95 p-3 shadow-sm backdrop-blur">
    <p class="mb-2 flex items-center gap-1.5 text-xs font-semibold text-gray-500">
      <span class="inline-block h-1.5 w-1.5 rounded-full bg-primary-500" />
      {{ title }}
    </p>

    <div class="flex flex-wrap gap-2">
      <button
        v-for="opt in options"
        :key="opt.intent + opt.label"
        class="rounded-lg border border-primary-200 bg-primary-50 px-3 py-1.5 text-xs font-medium text-primary-700 transition hover:bg-primary-100 disabled:cursor-not-allowed disabled:opacity-50"
        :disabled="busy"
        @click="pick(opt)"
      >
        {{ opt.label }}
      </button>
    </div>

    <p class="mt-2 text-[11px] leading-relaxed text-gray-400">
      {{ t('interview.choicesHint') }}
    </p>
  </div>
</template>
