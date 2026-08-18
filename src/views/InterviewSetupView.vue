<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useResumeStore } from '@/stores/resume'
import { useJdStore } from '@/stores/jd'
import { useInterviewStore } from '@/stores/interview'
import { getPositions } from '@/api/knowledge'
import DeviceCheckModal from '@/components/DeviceCheckModal.vue'
import InterviewTemplateSelector from '@/components/interview/InterviewTemplateSelector.vue'
import InterviewerSelectorModal from '@/components/interview/InterviewerSelectorModal.vue'
import type { Difficulty, InterviewerStyle, InterviewTemplate } from '@/types'

const { t } = useI18n()
const router = useRouter()
const resumeStore = useResumeStore()
const jdStore = useJdStore()
const interviewStore = useInterviewStore()

const position = ref('前端')
const difficulty = ref<Difficulty>('mid')
const duration = ref(30)
const style = ref<InterviewerStyle>('friendly')
const selectedResumeId = ref<number | undefined>(undefined)
const selectedJdId = ref<number | undefined>(undefined)
const starting = ref(false)
const showDeviceModal = ref(false)
const showInterviewerSelector = ref(false)
const selectedTemplate = ref<InterviewTemplate | null>(null)

function handleTemplateUpdate(t: InterviewTemplate | null) {
  selectedTemplate.value = t
  if (t) {
    position.value = t.position
    difficulty.value = t.difficulty
    duration.value = t.duration
    style.value = t.style
  }
}

// 兜底默认岗位列表（API 失败时使用）
const FALLBACK_POSITIONS = ['前端', '后端', '算法', '产品', '测试', '测试开发', '运维']
const positions = ref<string[]>([...FALLBACK_POSITIONS])
const difficulties: Difficulty[] = ['junior', 'mid', 'senior']
const durations = [15, 30, 45]
const styles: InterviewerStyle[] = ['strict', 'friendly', 'pressure']

// 简历管理
const resumeFileInput = ref<HTMLInputElement | null>(null)
const uploadPosition = ref('前端')
const uploading = ref(false)

// JD 管理
const jdFileInput = ref<HTMLInputElement | null>(null)
const jdTitle = ref('')
const jdContent = ref('')
const jdUploading = ref(false)
const jdCreating = ref(false)
const showJdForm = ref(false)

onMounted(async () => {
  resumeStore.fetchResumes()
  jdStore.fetchJds()
  try {
    const { positions: dbPositions } = await getPositions()
    if (dbPositions && dbPositions.length > 0) {
      positions.value = dbPositions
      // 默认选中第一个
      if (!positions.value.includes(position.value)) {
        position.value = positions.value[0]
      }
      if (!positions.value.includes(uploadPosition.value)) {
        uploadPosition.value = positions.value[0]
      }
    }
  } catch (e) {
    // API 失败则使用兜底列表
    console.warn('[Setup] fetch positions failed, using fallback', e)
  }
})

async function handleResumeUpload() {
  const file = resumeFileInput.value?.files?.[0]
  if (!file) return
  uploading.value = true
  try {
    await resumeStore.upload(file, uploadPosition.value)
    resumeFileInput.value!.value = ''
  } catch (e: any) {
    alert(e.message)
  } finally {
    uploading.value = false
  }
}

async function handleJdUpload() {
  const file = jdFileInput.value?.files?.[0]
  if (!file) return
  jdUploading.value = true
  try {
    const jd = await jdStore.uploadJd(file, '', position.value)
    selectedJdId.value = jd.id
    jdFileInput.value!.value = ''
  } catch (e: any) {
    alert(e.message)
  } finally {
    jdUploading.value = false
  }
}

async function handleJdCreate() {
  if (!jdTitle.value.trim() || !jdContent.value.trim()) {
    alert('请填写 JD 标题和内容')
    return
  }
  jdCreating.value = true
  try {
    const jd = await jdStore.createJd(jdTitle.value.trim(), jdContent.value.trim(), position.value)
    selectedJdId.value = jd.id
    jdTitle.value = ''
    jdContent.value = ''
    showJdForm.value = false
  } catch (e: any) {
    alert(e.message)
  } finally {
    jdCreating.value = false
  }
}

async function start() {
  showInterviewerSelector.value = true
}

function handleInterviewerConfirm() {
  showInterviewerSelector.value = false
  showDeviceModal.value = true
}

async function actuallyStart() {
  showDeviceModal.value = false
  starting.value = true
  try {
    await interviewStore.start({
      position: position.value,
      difficulty: difficulty.value,
      duration: duration.value,
      style: style.value,
      resumeId: selectedResumeId.value,
      jdId: selectedJdId.value,
    })
    router.push('/interview')
  } catch (e: any) {
    alert(e.message)
  } finally {
    starting.value = false
  }
}
</script>

<template>
  <div class="mx-auto max-w-2xl px-4 py-4 md:py-10">
    <button @click="router.back()" class="mb-4 text-sm text-gray-500 transition hover:text-primary-700">
      ← {{ t('common.back') }}
    </button>
    <h1 class="mb-6 text-xl md:text-2xl font-bold text-gray-900">{{ t('setup.title') }}</h1>

    <!-- 简历管理 -->
    <div class="card mb-4 md:mb-6">
      <h2 class="mb-4 text-lg font-semibold text-gray-800">{{ t('home.resumeMgmt') }}</h2>
      <div class="mb-3">
        <select
          v-model="uploadPosition"
          class="w-full rounded-lg border border-primary-200 bg-white px-3 py-2.5 text-sm min-h-[44px] focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100"
        >
          <option v-for="p in positions" :key="p" :value="p">{{ p }}</option>
        </select>
      </div>
      <input ref="resumeFileInput" type="file" accept=".pdf,.docx" class="hidden" @change="handleResumeUpload" />
      <button
        @click="resumeFileInput?.click()"
        :disabled="uploading"
        class="w-full rounded-xl border-2 border-dashed border-primary-200 px-4 py-5 md:py-6 text-sm text-primary-600 min-h-[44px] transition hover:border-primary-400 hover:bg-primary-50/50 disabled:opacity-60"
      >
        {{ uploading ? t('common.uploading') : t('home.uploadResume') }}
      </button>

      <!-- 简历列表loading -->
      <div v-if="resumeStore.loading" class="mt-3 space-y-2">
        <div v-for="i in 3" :key="i" class="h-12 animate-pulse rounded-lg bg-gray-100"></div>
      </div>
      <div v-else-if="resumeStore.resumes.length === 0" class="mt-3 text-sm text-gray-400">{{ t('home.noResumes') }}</div>
      <div v-else class="mt-3 space-y-2">
        <div
          v-for="resume in resumeStore.resumes"
          :key="resume.id"
          class="flex items-center justify-between rounded-lg bg-primary-50/50 px-3 py-2.5 min-h-[44px]"
        >
          <div class="min-w-0 flex-1">
            <p class="truncate text-sm font-medium text-gray-700">{{ resume.filename }}</p>
            <p class="text-xs text-gray-400">{{ t('home.matchScore') }}: {{ resume.analysisResult?.positionMatch || '-' }}%</p>
          </div>
          <div class="flex items-center gap-2">
            <button
              @click="router.push({ path: `/resume/${resume.id}/report`, query: { position: uploadPosition } })"
              class="text-sm text-primary-600 min-h-[36px] px-2 transition hover:text-primary-700"
            >
              详细报告
            </button>
            <button @click="resumeStore.remove(resume.id)" class="text-sm text-red-400 min-h-[36px] px-2 transition hover:text-red-600">
              {{ t('common.delete') }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- JD 库管理 -->
    <div class="card mb-4 md:mb-6">
      <div class="mb-4 flex items-center justify-between">
        <h2 class="text-lg font-semibold text-gray-800">岗位 JD 库</h2>
        <button
          @click="showJdForm = !showJdForm"
          class="text-sm text-primary-600 min-h-[36px] px-2 transition hover:text-primary-700"
        >
          {{ showJdForm ? '收起' : '+ 粘贴 JD' }}
        </button>
      </div>

      <!-- 粘贴创建 -->
      <div v-if="showJdForm" class="mb-4 space-y-2 rounded-lg bg-primary-50/40 p-3">
        <input
          v-model="jdTitle"
          placeholder="JD 标题（如：高级前端工程师）"
          class="w-full rounded-lg border border-primary-200 bg-white px-3 py-2.5 text-sm min-h-[44px] focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100"
        />
        <textarea
          v-model="jdContent"
          placeholder="粘贴 JD 全文..."
          rows="5"
          class="w-full rounded-lg border border-primary-200 bg-white px-3 py-2.5 text-sm focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100"
        />
        <button
          @click="handleJdCreate"
          :disabled="jdCreating"
          class="btn-primary w-full min-h-[44px]"
        >
          {{ jdCreating ? '保存中...' : '保存 JD' }}
        </button>
      </div>

      <!-- 文件上传 -->
      <input ref="jdFileInput" type="file" accept=".pdf,.docx,.md,.markdown,.txt" class="hidden" @change="handleJdUpload" />
      <button
        @click="jdFileInput?.click()"
        :disabled="jdUploading"
        class="w-full rounded-xl border-2 border-dashed border-primary-200 px-4 py-4 text-sm text-primary-600 min-h-[44px] transition hover:border-primary-400 hover:bg-primary-50/50 disabled:opacity-60"
      >
        {{ jdUploading ? '上传中...' : '上传 JD 文件（PDF / Markdown / Word）' }}
      </button>

      <!-- JD 列表loading -->
      <div v-if="jdStore.loading" class="mt-3 space-y-2">
        <div v-for="i in 2" :key="i" class="h-12 animate-pulse rounded-lg bg-gray-100"></div>
      </div>
      <div v-else-if="jdStore.jds.length === 0" class="mt-3 text-sm text-gray-400">暂无 JD，可粘贴或上传</div>
      <div v-else class="mt-3 space-y-2">
        <div
          v-for="jd in jdStore.jds"
          :key="jd.id"
          class="flex items-center justify-between rounded-lg bg-primary-50/50 px-3 py-2.5 min-h-[44px]"
        >
          <div class="min-w-0 flex-1">
            <p class="truncate text-sm font-medium text-gray-700">{{ jd.title }}</p>
            <p class="truncate text-xs text-gray-400">{{ jd.content.slice(0, 60) || '（空）' }}...</p>
          </div>
          <button @click="jdStore.deleteJd(jd.id)" class="ml-2 text-sm text-red-400 min-h-[36px] px-2 transition hover:text-red-600">
            删除
          </button>
        </div>
      </div>
    </div>

    <!-- 面试模板 -->
    <div class="card mb-4 md:mb-6">
      <InterviewTemplateSelector :model-value="selectedTemplate" @update:model-value="handleTemplateUpdate" />
    </div>

    <!-- 面试配置 -->
    <div class="card space-y-5 md:space-y-6">
      <div>
        <label class="mb-2 block text-sm font-medium text-gray-700">{{ t('setup.position') }}</label>
        <div class="flex flex-wrap gap-2">
          <button
            v-for="p in positions"
            :key="p"
            @click="position = p"
            :class="[
              'rounded-lg px-4 py-2 text-sm font-medium transition min-h-[36px]',
              position === p ? 'bg-gradient-brand text-white shadow-soft' : 'bg-primary-50/60 text-gray-700 hover:bg-primary-100',
            ]"
          >
            {{ p }}
          </button>
        </div>
      </div>

      <div>
        <label class="mb-2 block text-sm font-medium text-gray-700">{{ t('setup.difficulty') }}</label>
        <div class="flex gap-2">
          <button
            v-for="d in difficulties"
            :key="d"
            @click="difficulty = d"
            :class="[
              'rounded-lg px-5 py-2 text-sm font-medium transition min-h-[36px] flex-1',
              difficulty === d ? 'bg-gradient-brand text-white shadow-soft' : 'bg-primary-50/60 text-gray-700 hover:bg-primary-100',
            ]"
          >
            {{ t('difficulty.' + d) }}
          </button>
        </div>
      </div>

      <div>
        <label class="mb-2 block text-sm font-medium text-gray-700">{{ t('setup.duration') }}</label>
        <div class="flex gap-2">
          <button
            v-for="d in durations"
            :key="d"
            @click="duration = d"
            :class="[
              'rounded-lg px-5 py-2 text-sm font-medium transition min-h-[36px] flex-1',
              duration === d ? 'bg-gradient-brand text-white shadow-soft' : 'bg-primary-50/60 text-gray-700 hover:bg-primary-100',
            ]"
          >
            {{ d }}
          </button>
        </div>
      </div>

      <div>
        <label class="mb-2 block text-sm font-medium text-gray-700">{{ t('setup.interviewerStyle') }}</label>
        <div class="flex gap-2">
          <button
            v-for="s in styles"
            :key="s"
            @click="style = s"
            :class="[
              'rounded-lg px-5 py-2 text-sm font-medium transition min-h-[36px] flex-1',
              style === s ? 'bg-gradient-brand text-white shadow-soft' : 'bg-primary-50/60 text-gray-700 hover:bg-primary-100',
            ]"
          >
            {{ t('styles.' + s) }}
          </button>
        </div>
      </div>

      <div>
        <label class="mb-2 block text-sm font-medium text-gray-700">{{ t('setup.resume') }}</label>
        <select
          v-model="selectedResumeId"
          class="w-full rounded-lg border border-primary-200 bg-white px-3 py-2.5 text-sm min-h-[44px] focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100"
        >
          <option :value="undefined">{{ t('setup.noResume') }}</option>
          <option v-for="resume in resumeStore.resumes" :key="resume.id" :value="resume.id">
            {{ resume.filename }}
          </option>
        </select>
      </div>

      <div>
        <label class="mb-2 block text-sm font-medium text-gray-700">岗位 JD（可选，用于人岗匹配）</label>
        <select
          v-model="selectedJdId"
          class="w-full rounded-lg border border-primary-200 bg-white px-3 py-2.5 text-sm min-h-[44px] focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100"
        >
          <option :value="undefined">不使用 JD</option>
          <option v-for="jd in jdStore.jds" :key="jd.id" :value="jd.id">
            {{ jd.title }}
          </option>
        </select>
        <p class="mt-1 text-xs text-gray-400">选中后，面试官会针对 JD 要求出题，报告给出人岗匹配度</p>
      </div>

      <button
        @click="start"
        :disabled="starting"
        class="btn-primary w-full min-h-[52px] text-base"
      >
        {{ starting ? t('setup.starting') : t('setup.start') }}
      </button>
    </div>

    <!-- 面试官选择弹窗 -->
    <InterviewerSelectorModal
      :visible="showInterviewerSelector"
      @close="showInterviewerSelector = false"
      @confirm="handleInterviewerConfirm"
    />

    <!-- 设备调试 Modal -->
    <DeviceCheckModal
      :visible="showDeviceModal"
      @close="showDeviceModal = false"
      @start="actuallyStart"
    />
  </div>
</template>
