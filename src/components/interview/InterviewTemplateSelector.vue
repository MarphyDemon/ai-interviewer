<script setup lang="ts">
import { ref, computed } from 'vue'
import type { InterviewTemplate, Difficulty, InterviewerStyle } from '@/types'

const props = defineProps<{
  modelValue: InterviewTemplate | null
}>()

const emit = defineEmits<{
  'update:modelValue': [template: InterviewTemplate | null]
}>()

const selectedTemplate = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
})

const showCreateModal = ref(false)
const templates = ref<InterviewTemplate[]>([
  {
    id: 0,
    name: '前端基础面试',
    position: '前端',
    difficulty: 'junior',
    duration: 30,
    style: 'friendly',
    description: '针对应届毕业生 / 1 年经验，涵盖 HTML/CSS/JS 基础、Vue/React 入门',
    builtIn: true,
    createdAt: new Date().toISOString(),
  },
  {
    id: 1,
    name: '前端进阶面试',
    position: '前端',
    difficulty: 'mid',
    duration: 45,
    style: 'strict',
    description: '3-5 年经验，深入考察工程化、性能优化、架构设计',
    builtIn: true,
    createdAt: new Date().toISOString(),
  },
  {
    id: 2,
    name: '算法面试',
    position: '算法',
    difficulty: 'mid',
    duration: 45,
    style: 'pressure',
    description: '算法工程师岗位，侧重机器学习基础、SQL、系统设计',
    builtIn: true,
    createdAt: new Date().toISOString(),
  },
  {
    id: 3,
    name: '后端面试',
    position: '后端',
    difficulty: 'mid',
    duration: 45,
    style: 'friendly',
    description: 'Java/Go/Python 后端开发，分布式系统、微服务、数据库',
    builtIn: true,
    createdAt: new Date().toISOString(),
  },
  {
    id: 4,
    name: '产品经理面试',
    position: '产品',
    difficulty: 'mid',
    duration: 30,
    style: 'friendly',
    description: '需求分析、产品设计、数据分析、沟通协作',
    builtIn: true,
    createdAt: new Date().toISOString(),
  },
])

const newTemplate = ref<Partial<InterviewTemplate>>({
  name: '',
  position: '前端',
  difficulty: 'mid',
  duration: 30,
  style: 'friendly',
  description: '',
})

function selectTemplate(t: InterviewTemplate) {
  emit('update:modelValue', t)
}

function clearSelection() {
  emit('update:modelValue', null)
}

function createTemplate() {
  if (!newTemplate.value.name) return
  const t: InterviewTemplate = {
    id: Date.now(),
    name: newTemplate.value.name!,
    position: newTemplate.value.position!,
    difficulty: newTemplate.value.difficulty as Difficulty,
    duration: newTemplate.value.duration!,
    style: newTemplate.value.style as InterviewerStyle,
    description: newTemplate.value.description || '',
    builtIn: false,
    createdAt: new Date().toISOString(),
  }
  templates.value.push(t)
  selectTemplate(t)
  showCreateModal.value = false
  newTemplate.value = { name: '', position: '前端', difficulty: 'mid', duration: 30, style: 'friendly', description: '' }
}

function difficultyLabel(d: string) {
  return { junior: '初级', mid: '中级', senior: '高级' }[d] || d
}

function styleLabel(s: string) {
  return { strict: '严格', friendly: '友好', pressure: '压力面' }[s] || s
}
</script>

<template>
  <div>
    <div class="flex items-center justify-between mb-3">
      <h3 class="text-sm font-semibold text-gray-700">快速模板</h3>
      <div class="flex gap-2">
        <button @click="showCreateModal = true"
          class="text-xs text-blue-600 hover:text-blue-800">+ 自定义</button>
        <button v-if="selectedTemplate" @click="clearSelection"
          class="text-xs text-gray-500 hover:text-gray-700">清除选择</button>
      </div>
    </div>

    <div class="grid grid-cols-2 gap-2">
      <button
        v-for="t in templates"
        :key="t.id"
        @click="selectTemplate(t)"
        :class="[
          'text-left p-3 rounded-lg border transition',
          selectedTemplate?.id === t.id
            ? 'border-blue-500 bg-blue-50'
            : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50',
        ]"
      >
        <div class="flex items-center gap-1 mb-1">
          <span class="text-sm font-medium text-gray-900">{{ t.name }}</span>
          <span v-if="t.builtIn" class="text-xs px-1.5 py-0.5 bg-green-100 text-green-600 rounded">内置</span>
        </div>
        <div class="flex items-center gap-1 text-xs text-gray-500">
          <span>{{ t.position }}</span>
          <span>·</span>
          <span>{{ difficultyLabel(t.difficulty) }}</span>
          <span>·</span>
          <span>{{ t.duration }}分钟</span>
          <span>·</span>
          <span>{{ styleLabel(t.style) }}</span>
        </div>
        <p class="text-xs text-gray-500 mt-1 line-clamp-1">{{ t.description }}</p>
      </button>
    </div>

    <!-- 创建模板弹窗 -->
    <div v-if="showCreateModal" class="fixed inset-0 bg-black bg-opacity-30 flex items-center justify-center z-10">
      <div class="bg-white rounded-lg p-5 w-full max-w-sm mx-4">
        <h3 class="text-base font-semibold text-gray-900 mb-3">创建自定义模板</h3>
        <div class="space-y-2">
          <input v-model="newTemplate.name" placeholder="模板名称"
            class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
          <div class="grid grid-cols-2 gap-2">
            <select v-model="newTemplate.position"
              class="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500">
              <option>前端</option><option>后端</option><option>算法</option>
              <option>产品</option><option>测试</option><option>测试开发</option><option>运维</option>
            </select>
            <select v-model="newTemplate.difficulty"
              class="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500">
              <option value="junior">初级</option>
              <option value="mid">中级</option>
              <option value="senior">高级</option>
            </select>
            <select v-model="newTemplate.duration"
              class="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500">
              <option :value="15">15 分钟</option>
              <option :value="30">30 分钟</option>
              <option :value="45">45 分钟</option>
              <option :value="60">60 分钟</option>
            </select>
            <select v-model="newTemplate.style"
              class="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500">
              <option value="friendly">友好</option>
              <option value="strict">严格</option>
              <option value="pressure">压力面</option>
            </select>
          </div>
          <textarea v-model="newTemplate.description" placeholder="模板描述（可选）"
            class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm h-16 resize-none focus:ring-2 focus:ring-blue-500" />
        </div>
        <div class="flex gap-2 justify-end mt-3">
          <button @click="showCreateModal = false"
            class="px-3 py-1 text-sm text-gray-600 hover:bg-gray-100 rounded">取消</button>
          <button @click="createTemplate"
            class="px-3 py-1 bg-blue-600 text-white text-sm rounded hover:bg-blue-700">创建</button>
        </div>
      </div>
    </div>
  </div>
</template>