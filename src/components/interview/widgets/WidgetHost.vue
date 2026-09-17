<script setup lang="ts">
import { computed } from 'vue'
import type { InterviewWidget } from '@/types'
import { useInterviewEvents } from '@/composables/useInterviewEvents'
import ResumeHighlightWidget from './ResumeHighlightWidget.vue'
import MatchScoreWidget from './MatchScoreWidget.vue'
import QuestionCardWidget from './QuestionCardWidget.vue'
import JudgeResultWidget from './JudgeResultWidget.vue'
import InterviewReportWidget from './InterviewReportWidget.vue'
import ScoreWidget from './ScoreWidget.vue'
import PickerWidget from './PickerWidget.vue'

/**
 * Widget 宿主：按类型分发到具体组件，负责堆叠、关闭与动效。
 *
 * 布局策略（参考官方 CustomWidgetOverlay 每类卡片占固定区域的思路）：
 * 桌面端固定在具身交互智能体舞台右侧，移动端沉到底部，避免遮挡具身交互智能体正脸与输入区。
 */

const { widgets, removeWidget } = useInterviewEvents()

const registry = {
  resume_highlight: ResumeHighlightWidget,
  match_score: MatchScoreWidget,
  question_card: QuestionCardWidget,
  judge_result: JudgeResultWidget,
  interview_report: InterviewReportWidget,
  score: ScoreWidget,
  picker: PickerWidget,
} as const

type RegisteredType = keyof typeof registry

function componentOf(type: InterviewWidget['type']) {
  return registry[type as RegisteredType]
}

const visible = computed(() => widgets.value.filter((w) => w.type in registry))
</script>

<template>
  <div v-if="visible.length" class="widget-host">
    <TransitionGroup name="widget-pop" tag="div" class="flex flex-col gap-3">
      <div
        v-for="w in visible"
        :key="w.id"
        class="relative"
        role="region"
        :aria-label="`面试图表：${w.type}`"
      >
        <button
          class="absolute right-2 top-2 z-10 flex h-6 w-6 items-center justify-center rounded-full bg-black/30 text-xs text-white transition hover:bg-red-500/80"
          title="关闭"
          @click="removeWidget(w.id)"
        >
          ✕
        </button>
        <component :is="componentOf(w.type)" :data="w.data" />
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
/*
 * 锚定在具身交互智能体舞台底部（下三分之一），形成"下沿图文"的呈现效果：
 * - 不遮挡右侧对话区（桌面端右栏是用户气泡所在）
 * - 不遮挡具身交互智能体面部（角色通常居中偏上）
 * 容器本身不接收事件，只有卡片可交互，避免挡住底层画布操作。
 */
.widget-host {
  position: absolute;
  left: 0.5rem;
  right: 0.5rem;
  bottom: 0.5rem;
  z-index: 30;
  max-height: 72%;
  overflow-y: auto;
  pointer-events: none;
}

.widget-host > * {
  pointer-events: auto;
}

.widget-pop-enter-active,
.widget-pop-leave-active {
  transition: all 0.25s ease;
}
.widget-pop-enter-from {
  opacity: 0;
  transform: translateY(6px) scale(0.96);
}
.widget-pop-leave-to {
  opacity: 0;
  transform: translateY(-4px) scale(0.96);
}
</style>
