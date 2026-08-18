<script setup lang="ts">
import { ref, onMounted } from 'vue'

defineProps<{ show: boolean }>()
const emit = defineEmits<{ finish: [] }>()

const steps = [
  {
    title: '欢迎使用 AI 面试官',
    description: '我将带你快速了解如何使用这个平台进行 AI 模拟面试。整个过程只需 1 分钟。',
    icon: '👋',
  },
  {
    title: '准备简历和 JD',
    description: '上传你的简历 PDF 和目标岗位的 JD（职位描述），AI 将自动分析并匹配面试题目。',
    icon: '📄',
  },
  {
    title: '选择面试模板',
    description: '根据岗位和经验选择面试模板，或自定义面试参数（时长、难度、风格）。',
    icon: '🎯',
  },
  {
    title: '开始模拟面试',
    description: '通过语音或文字与数字人面试官进行多轮对话，AI 会实时评估你的回答质量。',
    icon: '💬',
  },
  {
    title: '查看详细报告',
    description: '面试结束后会生成完整的评估报告，包含各维度评分、问题回顾和改进建议。',
    icon: '📊',
  },
]

const currentStep = ref(0)
const totalSteps = steps.length

function next() {
  if (currentStep.value < totalSteps - 1) {
    currentStep.value++
  } else {
    finish()
  }
}

function prev() {
  if (currentStep.value > 0) currentStep.value--
}

function finish() {
  emit('finish')
  localStorage.setItem('onboarding_completed', 'true')
}

onMounted(() => {
  const completed = localStorage.getItem('onboarding_completed')
  if (completed) emit('finish')
})
</script>

<template>
  <Teleport to="body">
    <transition name="fade">
      <div v-if="show" class="fixed inset-0 bg-black bg-opacity-60 flex items-center justify-center z-50">
        <div class="bg-white rounded-2xl w-full max-w-md mx-4 overflow-hidden shadow-2xl">
          <!-- Progress bar -->
          <div class="h-1.5 bg-gray-100">
            <div
              class="h-full bg-gradient-brand transition-all duration-300"
              :style="{ width: `${((currentStep + 1) / totalSteps) * 100}%` }"
            ></div>
          </div>

          <div class="p-8">
            <!-- Step content -->
            <div class="text-center">
              <div class="text-5xl mb-4">{{ steps[currentStep].icon }}</div>
              <h2 class="text-xl font-semibold text-gray-900 mb-3">{{ steps[currentStep].title }}</h2>
              <p class="text-gray-600 leading-relaxed">{{ steps[currentStep].description }}</p>
            </div>

            <!-- Step indicators -->
            <div class="flex justify-center gap-2 mt-6">
              <span
                v-for="(_, i) in steps"
                :key="i"
                :class="[
                  'w-2 h-2 rounded-full transition-all',
                  i === currentStep ? 'bg-blue-600 w-6' : 'bg-gray-300',
                ]"
              ></span>
            </div>

            <!-- Actions -->
            <div class="flex items-center justify-between mt-6">
              <button
                @click="finish"
                class="text-sm text-gray-400 hover:text-gray-600"
              >
                跳过
              </button>
              <div class="flex gap-2">
                <button
                  v-if="currentStep > 0"
                  @click="prev"
                  class="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg"
                >
                  上一步
                </button>
                <button
                  @click="next"
                  class="px-5 py-2 bg-gradient-brand text-white text-sm rounded-lg hover:brightness-110"
                >
                  {{ currentStep === totalSteps - 1 ? '开始使用' : '下一步' }}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </transition>
  </Teleport>
</template>

<style scoped>
.fade-enter-active, .fade-leave-active {
  transition: opacity 0.3s ease;
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
}
</style>