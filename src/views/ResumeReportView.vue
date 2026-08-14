<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  generateResumeReport,
  getResumeReport,
  downloadResumeReportPdf,
  type ResumeReport,
} from '@/api/resume'
import { getPositions } from '@/api/knowledge'

const { t } = useI18n()
const router = useRouter()
const route = useRoute()
const props = defineProps<{ id: string }>()

const FALLBACK_POSITIONS = ['前端', '后端', '算法', '产品', '测试', '测试开发', '运维']
const positions = ref<string[]>([...FALLBACK_POSITIONS])
const selectedPosition = ref<string>('')

const report = ref<ResumeReport | null>(null)
const loading = ref(true)
const generating = ref(false)
const exporting = ref(false)
const errorMsg = ref('')

onMounted(async () => {
  // 拉取岗位列表
  try {
    const { positions: dbPositions } = await getPositions()
    if (dbPositions && dbPositions.length > 0) {
      positions.value = dbPositions
    }
  } catch {
    // 使用兜底
  }

  // 从 query 读取预设岗位
  const queryPos = route.query.position as string
  if (queryPos) {
    selectedPosition.value = queryPos
    await loadReport()
  } else {
    loading.value = false
  }
})

async function loadReport() {
  if (!selectedPosition.value) {
    errorMsg.value = '请先选择目标岗位'
    return
  }
  loading.value = true
  errorMsg.value = ''
  try {
    try {
      report.value = await getResumeReport(Number(props.id), selectedPosition.value)
    } catch (e: any) {
      // 404 表示尚未生成，不报错，等待用户点生成
      if (e?.status === 404 || /not found/i.test(e.message || '')) {
        report.value = null
      } else {
        throw e
      }
    }
  } catch (e: any) {
    errorMsg.value = e.message || '加载失败'
  } finally {
    loading.value = false
  }
}

async function generate() {
  if (!selectedPosition.value) {
    errorMsg.value = '请先选择目标岗位'
    return
  }
  generating.value = true
  errorMsg.value = ''
  try {
    report.value = await generateResumeReport(Number(props.id), selectedPosition.value)
  } catch (e: any) {
    errorMsg.value = e.message || '生成失败'
  } finally {
    generating.value = false
  }
}

async function exportPDF() {
  if (!report.value) return
  exporting.value = true
  try {
    await downloadResumeReportPdf(Number(props.id), selectedPosition.value)
  } catch (e: any) {
    errorMsg.value = e.message || 'PDF 导出失败'
  } finally {
    exporting.value = false
  }
}

const gradeColor = computed(() => {
  switch (report.value?.grade) {
    case 'S': return 'text-purple-600'
    case 'A': return 'text-green-600'
    case 'B': return 'text-blue-600'
    case 'C': return 'text-amber-600'
    case 'D': return 'text-red-600'
    default: return 'text-gray-600'
  }
})

function scoreColor(score: number): string {
  if (score >= 80) return 'bg-green-500'
  if (score >= 60) return 'bg-blue-500'
  if (score >= 40) return 'bg-amber-500'
  return 'bg-red-500'
}
</script>

<template>
  <div class="mx-auto max-w-3xl px-4 py-10">
    <button @click="router.back()" class="mb-6 text-sm text-gray-500 transition hover:text-primary-700">
      ← {{ t('common.back') }}
    </button>
    <h1 class="mb-6 text-2xl font-bold text-gray-900">简历深度评估报告</h1>

    <!-- 岗位选择 -->
    <div class="card mb-6">
      <label class="mb-2 block text-sm font-medium text-gray-700">目标岗位</label>
      <div class="flex gap-2">
        <select
          v-model="selectedPosition"
          :disabled="generating"
          class="flex-1 rounded-lg border border-primary-200 bg-white px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100 disabled:opacity-60"
          @change="loadReport"
        >
          <option value="" disabled>请选择岗位</option>
          <option v-for="p in positions" :key="p" :value="p">{{ p }}</option>
        </select>
        <button
          v-if="!report"
          @click="generate"
          :disabled="!selectedPosition || generating"
          class="btn-primary !py-2"
        >
          {{ generating ? '生成中...' : '生成报告' }}
        </button>
        <button
          v-else
          @click="generate"
          :disabled="!selectedPosition || generating"
          class="rounded-lg bg-primary-50 px-3 py-2 text-sm font-medium text-primary-700 transition hover:bg-primary-100 disabled:opacity-50"
        >
          {{ generating ? '重新生成中...' : '重新生成' }}
        </button>
      </div>
    </div>

    <div v-if="loading" class="py-20 text-center text-gray-400">{{ t('common.loading') }}</div>
    <div v-else-if="errorMsg" class="py-20 text-center text-red-500">{{ errorMsg }}</div>

    <div v-else-if="!selectedPosition" class="py-20 text-center text-gray-400">
      请选择目标岗位后生成报告
    </div>

    <div v-else-if="!report" class="py-20 text-center text-gray-400">
      尚无该岗位的评估报告，点击「生成报告」按钮创建
    </div>

    <div v-else-if="report" class="space-y-6">
      <!-- 综合评级 -->
      <div class="card">
        <div class="flex items-center justify-around">
          <div class="text-center">
            <p class="text-sm text-gray-400">综合评级</p>
            <p :class="['text-6xl font-bold', gradeColor]">{{ report.grade }}</p>
            <p class="mt-1 text-xs text-gray-400">S=优秀 / A=良好 / B=合格 / C=待提升 / D=不合格</p>
          </div>
          <div class="text-center">
            <p class="text-sm text-gray-400">目标岗位</p>
            <p class="mt-2 text-xl font-semibold text-gray-800">{{ report.position }}</p>
            <p class="mt-1 text-xs text-gray-400">{{ new Date(report.createdAt).toLocaleString('zh-CN') }}</p>
          </div>
        </div>
      </div>

      <!-- 评分维度 -->
      <div class="card">
        <h3 class="mb-4 font-semibold text-gray-700">评分维度</h3>
        <div class="space-y-3">
          <div>
            <div class="mb-1 flex justify-between text-sm">
              <span class="text-gray-600">结构完整度</span>
              <span class="font-medium text-gray-800">{{ report.data.structureScore }}</span>
            </div>
            <div class="h-2 rounded-full bg-gray-200">
              <div :class="['h-2 rounded-full', scoreColor(report.data.structureScore)]" :style="{ width: report.data.structureScore + '%' }"></div>
            </div>
          </div>
          <div>
            <div class="mb-1 flex justify-between text-sm">
              <span class="text-gray-600">岗位匹配度</span>
              <span class="font-medium text-gray-800">{{ report.data.positionMatch }}%</span>
            </div>
            <div class="h-2 rounded-full bg-gray-200">
              <div :class="['h-2 rounded-full', scoreColor(report.data.positionMatch)]" :style="{ width: report.data.positionMatch + '%' }"></div>
            </div>
          </div>
          <div>
            <div class="mb-1 flex justify-between text-sm">
              <span class="text-gray-600">技能覆盖度</span>
              <span class="font-medium text-gray-800">{{ report.data.skillCoverage }}</span>
            </div>
            <div class="h-2 rounded-full bg-gray-200">
              <div :class="['h-2 rounded-full', scoreColor(report.data.skillCoverage)]" :style="{ width: report.data.skillCoverage + '%' }"></div>
            </div>
          </div>
          <div>
            <div class="mb-1 flex justify-between text-sm">
              <span class="text-gray-600">项目深度</span>
              <span class="font-medium text-gray-800">{{ report.data.projectDepth }}</span>
            </div>
            <div class="h-2 rounded-full bg-gray-200">
              <div :class="['h-2 rounded-full', scoreColor(report.data.projectDepth)]" :style="{ width: report.data.projectDepth + '%' }"></div>
            </div>
          </div>
        </div>
      </div>

      <!-- 亮点 -->
      <div v-if="report.data.highlights.length" class="card">
        <h3 class="mb-3 font-semibold text-gray-700">亮点</h3>
        <ul class="space-y-2">
          <li v-for="(h, i) in report.data.highlights" :key="i" class="flex gap-2 text-sm text-gray-700">
            <span class="text-green-500">✓</span>
            <span>{{ h }}</span>
          </li>
        </ul>
      </div>

      <!-- 不足 -->
      <div v-if="report.data.weaknesses.length" class="card">
        <h3 class="mb-3 font-semibold text-gray-700">不足</h3>
        <ul class="space-y-2">
          <li v-for="(w, i) in report.data.weaknesses" :key="i" class="flex gap-2 text-sm text-gray-700">
            <span class="text-red-500">✗</span>
            <span>{{ w }}</span>
          </li>
        </ul>
      </div>

      <!-- 改进建议 -->
      <div v-if="report.data.improvements.length" class="card">
        <h3 class="mb-3 font-semibold text-gray-700">改进建议</h3>
        <div class="space-y-3">
          <div v-for="(imp, i) in report.data.improvements" :key="i" class="border-l-4 border-primary-200 pl-3">
            <p class="mb-1 text-sm font-medium text-gray-800">{{ imp.section }}</p>
            <p class="text-sm text-gray-600">{{ imp.suggestion }}</p>
          </div>
        </div>
      </div>

      <!-- 可投递岗位 -->
      <div v-if="report.data.recommendedPositions.length" class="card">
        <h3 class="mb-3 font-semibold text-gray-700">可投递岗位建议</h3>
        <div class="flex flex-wrap gap-2">
          <span
            v-for="(p, i) in report.data.recommendedPositions"
            :key="i"
            class="rounded-full bg-primary-50 px-3 py-1 text-sm text-primary-700"
          >
            {{ p }}
          </span>
        </div>
      </div>

      <!-- 操作 -->
      <div class="flex gap-4">
        <button
          @click="exportPDF"
          :disabled="exporting"
          class="btn-primary !py-2"
        >
          {{ exporting ? t('common.loading') : '导出 PDF' }}
        </button>
      </div>
    </div>
  </div>
</template>
