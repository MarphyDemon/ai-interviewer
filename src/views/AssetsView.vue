<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useResumeStore } from '@/stores/resume'
import { useJdStore } from '@/stores/jd'
import { getPositions } from '@/api/knowledge'
import type { JobDescription } from '@/types'

const { t } = useI18n()
const router = useRouter()
const resumeStore = useResumeStore()
const jdStore = useJdStore()

// 岗位方向：简历分析时使用；JD 仅作为可选归类标签
const FALLBACK_POSITIONS = ['前端', '后端', '算法', '产品', '测试', '测试开发', '运维']
const positions = ref<string[]>([...FALLBACK_POSITIONS])
const position = ref('前端')

onMounted(async () => {
  resumeStore.fetchResumes()
  jdStore.fetchJds()
  try {
    const { positions: dbPositions } = await getPositions()
    if (dbPositions && dbPositions.length > 0) {
      positions.value = dbPositions
      if (!positions.value.includes(position.value)) position.value = positions.value[0]
    }
  } catch (e) {
    console.warn('[Assets] fetch positions failed, using fallback', e)
  }
})

/* ---------------- 简历 ---------------- */
const resumeFileInput = ref<HTMLInputElement | null>(null)
const uploadingResume = ref(false)
const editingResumeId = ref<number | null>(null)
const editingResumeName = ref('')
const savingResume = ref(false)

async function handleResumeUpload() {
  const file = resumeFileInput.value?.files?.[0]
  if (!file) return
  uploadingResume.value = true
  try {
    await resumeStore.upload(file, position.value)
    resumeFileInput.value!.value = ''
  } catch (e: any) {
    alert(e.message)
  } finally {
    uploadingResume.value = false
  }
}

function startRenameResume(id: number, name: string) {
  editingResumeId.value = id
  editingResumeName.value = name
}

function cancelRenameResume() {
  editingResumeId.value = null
  editingResumeName.value = ''
}

async function confirmRenameResume() {
  const name = editingResumeName.value.trim()
  if (!name) {
    alert(t('assets.resumes.renameRequired'))
    return
  }
  savingResume.value = true
  try {
    await resumeStore.rename(editingResumeId.value!, name)
    cancelRenameResume()
  } catch (e: any) {
    alert(t('assets.resumes.renameFailed') + e.message)
  } finally {
    savingResume.value = false
  }
}

async function removeResume(id: number) {
  if (!confirm(t('assets.resumes.deleteConfirm'))) return
  try {
    await resumeStore.remove(id)
  } catch (e: any) {
    alert(e.message)
  }
}

/* ---------------- 岗位 JD ---------------- */
const jdFileInput = ref<HTMLInputElement | null>(null)
const uploadingJd = ref(false)
const jdCreating = ref(false)
const showJdForm = ref(false)
const jdTitle = ref('')
const jdContent = ref('')
const editingJdId = ref<number | null>(null)
const editingJdTitle = ref('')
const editingJdContent = ref('')
const savingJd = ref(false)

async function handleJdUpload() {
  const file = jdFileInput.value?.files?.[0]
  if (!file) return
  uploadingJd.value = true
  try {
    await jdStore.uploadJd(file, '', position.value)
    jdFileInput.value!.value = ''
  } catch (e: any) {
    alert(e.message)
  } finally {
    uploadingJd.value = false
  }
}

async function handleJdCreate() {
  if (!jdTitle.value.trim() || !jdContent.value.trim()) {
    alert(t('assets.jds.titleContentRequired'))
    return
  }
  jdCreating.value = true
  try {
    await jdStore.createJd(jdTitle.value.trim(), jdContent.value.trim(), position.value)
    jdTitle.value = ''
    jdContent.value = ''
    showJdForm.value = false
  } catch (e: any) {
    alert(e.message)
  } finally {
    jdCreating.value = false
  }
}

function startEditJd(jd: JobDescription) {
  editingJdId.value = jd.id
  editingJdTitle.value = jd.title
  editingJdContent.value = jd.content
}

function cancelEditJd() {
  editingJdId.value = null
  editingJdTitle.value = ''
  editingJdContent.value = ''
}

async function confirmEditJd() {
  if (!editingJdTitle.value.trim() || !editingJdContent.value.trim()) {
    alert(t('assets.jds.titleContentRequired'))
    return
  }
  savingJd.value = true
  try {
    await jdStore.updateJd(editingJdId.value!, {
      title: editingJdTitle.value.trim(),
      content: editingJdContent.value,
    })
    cancelEditJd()
  } catch (e: any) {
    alert(e.message)
  } finally {
    savingJd.value = false
  }
}

async function removeJd(id: number) {
  if (!confirm(t('assets.jds.deleteConfirm'))) return
  try {
    await jdStore.deleteJd(id)
  } catch (e: any) {
    alert(e.message)
  }
}

function summary(content: string): string {
  return content.replace(/\s+/g, ' ').slice(0, 60) || t('assets.jds.emptyContent')
}
</script>

<template>
  <div class="mx-auto max-w-2xl px-4 py-4 md:py-10">
    <button @click="router.back()" class="mb-4 text-sm text-gray-500 transition hover:text-primary-700">
      ← {{ t('common.back') }}
    </button>
    <h1 class="mb-1 text-xl md:text-2xl font-bold text-gray-900">{{ t('assets.title') }}</h1>
    <p class="mb-6 text-sm text-gray-500">{{ t('assets.subtitle') }}</p>

    <!-- 岗位方向：简历分析使用；JD 作为可选归类标签 -->
    <div class="card mb-4 md:mb-6">
      <label class="mb-2 block text-sm font-medium text-gray-700">{{ t('assets.positionLabel') }}</label>
      <select
        v-model="position"
        class="w-full rounded-lg border border-primary-200 bg-white px-3 py-2.5 text-sm min-h-[44px] focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100"
      >
        <option v-for="p in positions" :key="p" :value="p">{{ p }}</option>
      </select>
    </div>

    <!-- 简历 -->
    <div class="card mb-4 md:mb-6">
      <h2 class="mb-4 text-lg font-semibold text-gray-800">{{ t('assets.resumes.title') }}</h2>

      <input
        ref="resumeFileInput"
        type="file"
        accept=".pdf,.docx"
        class="hidden"
        @change="handleResumeUpload"
      />
      <button
        @click="resumeFileInput?.click()"
        :disabled="uploadingResume"
        class="w-full rounded-xl border-2 border-dashed border-primary-200 px-4 py-5 md:py-6 text-sm text-primary-600 min-h-[44px] transition hover:border-primary-400 hover:bg-primary-50/50 disabled:opacity-60"
      >
        {{ uploadingResume ? t('common.uploading') : t('assets.resumes.upload') }}
      </button>

      <div v-if="resumeStore.loading" class="mt-3 space-y-2">
        <div v-for="i in 3" :key="i" class="h-12 animate-pulse rounded-lg bg-gray-100"></div>
      </div>
      <div v-else-if="resumeStore.resumes.length === 0" class="mt-3 text-sm text-gray-400">
        {{ t('assets.resumes.empty') }}
      </div>
      <div v-else class="mt-3 space-y-2">
        <div
          v-for="resume in resumeStore.resumes"
          :key="resume.id"
          class="rounded-lg bg-primary-50/50 px-3 py-2.5"
        >
          <div class="flex items-center justify-between gap-2 min-h-[44px]">
            <div class="min-w-0 flex-1">
              <p class="truncate text-sm font-medium text-gray-700">{{ resume.filename }}</p>
              <p class="text-xs text-gray-400">
                {{ t('assets.resumes.matchScore') }}: {{ resume.analysisResult?.positionMatch ?? '-' }}%
              </p>
            </div>
            <div class="flex items-center gap-1">
              <button
                @click="startRenameResume(resume.id, resume.filename)"
                class="text-sm text-primary-600 min-h-[36px] px-2 transition hover:text-primary-700"
              >
                {{ t('assets.resumes.rename') }}
              </button>
              <button
                @click="router.push({ path: `/resume/${resume.id}/report`, query: { position } })"
                class="text-sm text-primary-600 min-h-[36px] px-2 transition hover:text-primary-700"
              >
                {{ t('assets.resumes.detailReport') }}
              </button>
              <button
                @click="removeResume(resume.id)"
                class="text-sm text-red-400 min-h-[36px] px-2 transition hover:text-red-600"
              >
                {{ t('common.delete') }}
              </button>
            </div>
          </div>

          <!-- 重命名 -->
          <div v-if="editingResumeId === resume.id" class="mt-2 flex gap-2">
            <input
              v-model="editingResumeName"
              :placeholder="t('assets.resumes.renamePlaceholder')"
              class="min-w-0 flex-1 rounded-lg border border-primary-200 bg-white px-3 py-2 text-sm min-h-[40px] focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100"
            />
            <button
              @click="confirmRenameResume"
              :disabled="savingResume"
              class="btn-primary !px-3 !py-2 text-sm min-h-[40px]"
            >
              {{ t('common.save') }}
            </button>
            <button @click="cancelRenameResume" class="btn-ghost !px-3 !py-2 text-sm min-h-[40px]">
              {{ t('common.cancel') }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 岗位 JD -->
    <div class="card mb-4 md:mb-6">
      <div class="mb-4 flex items-center justify-between">
        <h2 class="text-lg font-semibold text-gray-800">{{ t('assets.jds.title') }}</h2>
        <button
          @click="showJdForm = !showJdForm"
          class="text-sm text-primary-600 min-h-[36px] px-2 transition hover:text-primary-700"
        >
          {{ showJdForm ? t('assets.jds.collapse') : t('assets.jds.pasteToggle') }}
        </button>
      </div>

      <div v-if="showJdForm" class="mb-4 space-y-2 rounded-lg bg-primary-50/40 p-3">
        <input
          v-model="jdTitle"
          :placeholder="t('assets.jds.titlePlaceholder')"
          class="w-full rounded-lg border border-primary-200 bg-white px-3 py-2.5 text-sm min-h-[44px] focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100"
        />
        <textarea
          v-model="jdContent"
          :placeholder="t('assets.jds.contentPlaceholder')"
          rows="5"
          class="w-full rounded-lg border border-primary-200 bg-white px-3 py-2.5 text-sm focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100"
        />
        <button
          @click="handleJdCreate"
          :disabled="jdCreating"
          class="btn-primary w-full min-h-[44px]"
        >
          {{ jdCreating ? t('assets.jds.saving') : t('assets.jds.create') }}
        </button>
      </div>

      <input
        ref="jdFileInput"
        type="file"
        accept=".pdf,.docx,.md,.markdown,.txt"
        class="hidden"
        @change="handleJdUpload"
      />
      <button
        @click="jdFileInput?.click()"
        :disabled="uploadingJd"
        class="w-full rounded-xl border-2 border-dashed border-primary-200 px-4 py-4 text-sm text-primary-600 min-h-[44px] transition hover:border-primary-400 hover:bg-primary-50/50 disabled:opacity-60"
      >
        {{ uploadingJd ? t('common.uploading') : t('assets.jds.upload') }}
      </button>

      <div v-if="jdStore.loading" class="mt-3 space-y-2">
        <div v-for="i in 2" :key="i" class="h-12 animate-pulse rounded-lg bg-gray-100"></div>
      </div>
      <div v-else-if="jdStore.jds.length === 0" class="mt-3 text-sm text-gray-400">
        {{ t('assets.jds.empty') }}
      </div>
      <div v-else class="mt-3 space-y-2">
        <div v-for="jd in jdStore.jds" :key="jd.id" class="rounded-lg bg-primary-50/50 px-3 py-2.5">
          <div class="flex items-center justify-between gap-2">
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2">
                <p class="truncate text-sm font-medium text-gray-700">{{ jd.title }}</p>
                <span
                  v-if="jd.orgId"
                  class="shrink-0 rounded bg-amber-50 px-1.5 py-0.5 text-[10px] text-amber-700"
                >
                  {{ t('assets.jds.orgShared') }}
                </span>
              </div>
              <p class="truncate text-xs text-gray-400">{{ summary(jd.content) }}...</p>
            </div>
            <div v-if="jd.canManage" class="flex shrink-0 items-center gap-1">
              <button
                @click="startEditJd(jd)"
                class="text-sm text-primary-600 min-h-[36px] px-2 transition hover:text-primary-700"
              >
                {{ t('common.edit') }}
              </button>
              <button
                @click="removeJd(jd.id)"
                class="text-sm text-red-400 min-h-[36px] px-2 transition hover:text-red-600"
              >
                {{ t('common.delete') }}
              </button>
            </div>
            <span v-else class="shrink-0 text-xs text-gray-400">{{ t('assets.jds.readOnly') }}</span>
          </div>

          <!-- 编辑 -->
          <div v-if="editingJdId === jd.id" class="mt-2 space-y-2">
            <input
              v-model="editingJdTitle"
              :placeholder="t('assets.jds.titlePlaceholder')"
              class="w-full rounded-lg border border-primary-200 bg-white px-3 py-2 text-sm min-h-[40px] focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100"
            />
            <textarea
              v-model="editingJdContent"
              :placeholder="t('assets.jds.contentPlaceholder')"
              rows="5"
              class="w-full rounded-lg border border-primary-200 bg-white px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100"
            />
            <div class="flex gap-2">
              <button
                @click="confirmEditJd"
                :disabled="savingJd"
                class="btn-primary flex-1 min-h-[40px] text-sm"
              >
                {{ savingJd ? t('assets.jds.saving') : t('common.save') }}
              </button>
              <button @click="cancelEditJd" class="btn-ghost flex-1 min-h-[40px] text-sm">
                {{ t('common.cancel') }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
