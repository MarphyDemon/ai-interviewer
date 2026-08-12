<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useKnowledgeStore } from '@/stores/knowledge'
import { useResumeStore } from '@/stores/resume'
import LangToggle from '@/components/common/LangToggle.vue'

const { t } = useI18n()
const router = useRouter()
const knowledgeStore = useKnowledgeStore()
const resumeStore = useResumeStore()

const knowledgeFileInput = ref<HTMLInputElement | null>(null)
const resumeFileInput = ref<HTMLInputElement | null>(null)
const uploadPosition = ref('frontend')
const uploading = ref(false)

const positions = ['frontend', 'backend', 'algorithm', 'product'] as const

onMounted(() => {
  knowledgeStore.fetchDocs()
  resumeStore.fetchResumes()
})

async function handleKnowledgeUpload() {
  const files = knowledgeFileInput.value?.files
  if (!files || files.length === 0) return
  uploading.value = true
  try {
    await knowledgeStore.upload(Array.from(files))
    knowledgeFileInput.value!.value = ''
  } catch (e: any) {
    alert(e.message)
  } finally {
    uploading.value = false
  }
}

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

function startInterview() {
  router.push('/setup')
}
</script>

<template>
  <div class="min-h-screen bg-gray-50">
    <div class="mx-auto max-w-4xl px-4 py-8">
      <div class="mb-8 flex items-center justify-between">
        <h1 class="text-3xl font-bold text-gray-800">{{ t('nav.home') }}</h1>
        <LangToggle />
      </div>

      <div class="mb-6 flex gap-4">
        <button
          @click="startInterview"
          class="rounded-lg bg-primary-600 px-6 py-3 text-white font-medium hover:bg-primary-700 transition"
        >
          {{ t('nav.startInterview') }}
        </button>
        <button
          @click="router.push('/history')"
          class="rounded-lg border border-gray-300 px-6 py-3 text-gray-700 font-medium hover:bg-gray-100 transition"
        >
          {{ t('nav.history') }}
        </button>
        <button
          @click="router.push('/admin')"
          class="rounded-lg border border-gray-300 px-6 py-3 text-gray-700 font-medium hover:bg-gray-100 transition"
        >
          {{ t('nav.admin') }}
        </button>
      </div>

      <div class="grid gap-6 md:grid-cols-2">
        <div class="rounded-lg bg-white p-6 shadow-sm">
          <h2 class="mb-4 text-xl font-semibold text-gray-700">{{ t('home.knowledgeMgmt') }}</h2>
          <div class="mb-4">
            <input
              ref="knowledgeFileInput"
              type="file"
              accept=".md"
              multiple
              class="hidden"
              @change="handleKnowledgeUpload"
            />
            <button
              @click="knowledgeFileInput?.click()"
              :disabled="uploading"
              class="w-full rounded-lg border-2 border-dashed border-gray-300 px-4 py-6 text-gray-500 hover:border-primary-400 hover:text-primary-600 transition"
            >
              {{ uploading ? t('common.uploading') : t('home.uploadMd') }}
            </button>
          </div>
          <div v-if="knowledgeStore.docs.length === 0" class="text-sm text-gray-400">
            {{ t('home.noDocs') }}
          </div>
          <div v-else class="space-y-2">
            <div
              v-for="doc in knowledgeStore.docs"
              :key="doc.id"
              class="flex items-center justify-between rounded-md bg-gray-50 px-3 py-2"
            >
              <div>
                <p class="text-sm font-medium text-gray-700">{{ doc.title || doc.filename }}</p>
                <p class="text-xs text-gray-400">
                  {{ t('positions.' + doc.position, doc.position) }} ·
                  {{ t('difficulty.' + doc.difficulty, doc.difficulty) }} ·
                  <span :class="{
                    'text-yellow-500': doc.status === 'processing',
                    'text-green-500': doc.status === 'ready',
                    'text-red-500': doc.status === 'failed',
                  }">{{ doc.status }}</span>
                </p>
              </div>
              <button
                @click="knowledgeStore.remove(doc.id)"
                class="text-sm text-red-400 hover:text-red-600"
              >
                {{ t('common.delete') }}
              </button>
            </div>
          </div>
        </div>

        <div class="rounded-lg bg-white p-6 shadow-sm">
          <h2 class="mb-4 text-xl font-semibold text-gray-700">{{ t('home.resumeMgmt') }}</h2>
          <div class="mb-2">
            <select
              v-model="uploadPosition"
              class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
            >
              <option v-for="p in positions" :key="p" :value="p">{{ t('positions.' + p) }}</option>
            </select>
          </div>
          <div class="mb-4">
            <input
              ref="resumeFileInput"
              type="file"
              accept=".pdf,.docx"
              class="hidden"
              @change="handleResumeUpload"
            />
            <button
              @click="resumeFileInput?.click()"
              :disabled="uploading"
              class="w-full rounded-lg border-2 border-dashed border-gray-300 px-4 py-6 text-gray-500 hover:border-primary-400 hover:text-primary-600 transition"
            >
              {{ uploading ? t('common.uploading') : t('home.uploadResume') }}
            </button>
          </div>
          <div v-if="resumeStore.resumes.length === 0" class="text-sm text-gray-400">
            {{ t('home.noResumes') }}
          </div>
          <div v-else class="space-y-2">
            <div
              v-for="resume in resumeStore.resumes"
              :key="resume.id"
              class="flex items-center justify-between rounded-md bg-gray-50 px-3 py-2"
            >
              <div>
                <p class="text-sm font-medium text-gray-700">{{ resume.filename }}</p>
                <p class="text-xs text-gray-400">
                  {{ t('home.matchScore') }}: {{ resume.analysisResult?.positionMatch || '-' }}%
                </p>
              </div>
              <button
                @click="resumeStore.remove(resume.id)"
                class="text-sm text-red-400 hover:text-red-600"
              >
                {{ t('common.delete') }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
