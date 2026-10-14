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

// 简历快捷上传（列表为空时使用；完整管理在 /assets）
const resumeFileInput = ref<HTMLInputElement | null>(null)
const uploading = ref(false)

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
    await resumeStore.upload(file, position.value)
    resumeFileInput.value!.value = ''
  } catch (e: any) {
    alert(e.message)
  } finally {
    uploading.value = false
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
        <!-- 列表为空时提供快捷上传，避免"没有简历可选"的死胡同；完整管理在 /assets -->
        <input
          ref="resumeFileInput"
          type="file"
          accept=".pdf,.docx"
          class="hidden"
          @change="handleResumeUpload"
        />
        <button
          v-if="resumeStore.resumes.length === 0"
          @click="resumeFileInput?.click()"
          :disabled="uploading"
          class="mt-2 w-full rounded-lg border-2 border-dashed border-primary-200 px-4 py-3 text-sm text-primary-600 min-h-[44px] transition hover:border-primary-400 hover:bg-primary-50/50 disabled:opacity-60"
        >
          {{ uploading ? t('common.uploading') : t('setup.quickUploadResume') }}
        </button>
        <button
          class="mt-1 text-xs text-primary-600 transition hover:text-primary-700"
          @click="router.push('/assets')"
        >
          {{ t('setup.manageAssets') }} →
        </button>
      </div>

      <div>
        <label class="mb-2 block text-sm font-medium text-gray-700">{{ t('setup.jd') }}</label>
        <select
          v-model="selectedJdId"
          class="w-full rounded-lg border border-primary-200 bg-white px-3 py-2.5 text-sm min-h-[44px] focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100"
        >
          <option :value="undefined">{{ t('setup.noJd') }}</option>
          <option v-for="jd in jdStore.jds" :key="jd.id" :value="jd.id">
            {{ jd.orgId ? `${jd.title}（${t('assets.jds.orgShared')}）` : jd.title }}
          </option>
        </select>
        <p class="mt-1 text-xs text-gray-400">{{ t('setup.jdHint') }}</p>
        <button
          class="mt-1 text-xs text-primary-600 transition hover:text-primary-700"
          @click="router.push('/assets')"
        >
          {{ t('setup.manageAssets') }} →
        </button>
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
