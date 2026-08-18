<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import * as knowledgeApi from '@/api/knowledge'
import { useKnowledgeStore } from '@/stores/knowledge'
import VersionHistory from '@/components/knowledge/VersionHistory.vue'
import CollaboratorManager from '@/components/knowledge/CollaboratorManager.vue'
import KnowledgeAgreementModal from '@/components/knowledge/KnowledgeAgreementModal.vue'

const FALLBACK_POSITIONS = ['前端', '后端', '算法', '产品', '测试', '测试开发', '运维']
const ALL_TAB = '__all__'

const { t } = useI18n()
const knowledgeStore = useKnowledgeStore()

const knowledgeFileInput = ref<HTMLInputElement | null>(null)
const uploading = ref(false)
const showAgreement = ref(false)
const knowledgeDeletingId = ref<number | null>(null)
const showVersionHistoryId = ref<number | null>(null)
const showCollaboratorDocId = ref<number | null>(null)

const positionTabs = ref<string[]>([...FALLBACK_POSITIONS])
const activePosition = ref<string>(ALL_TAB)
const searchQuery = ref('')
const activeTag = ref<string>('')

const allTags = computed(() => {
  const tags = new Set<string>()
  knowledgeStore.docs.forEach((d) => {
    if (d.tags) d.tags.forEach((tag) => tags.add(tag))
  })
  return Array.from(tags).sort()
})

const filteredDocs = computed(() => {
  let docs = knowledgeStore.docs
  if (activePosition.value !== ALL_TAB) {
    docs = docs.filter((d) => d.position === activePosition.value)
  }
  if (activeTag.value) {
    docs = docs.filter((d) => d.tags?.includes(activeTag.value))
  }
  if (searchQuery.value.trim()) {
    const q = searchQuery.value.trim().toLowerCase()
    docs = docs.filter(
      (d) =>
        d.title?.toLowerCase().includes(q) ||
        d.filename?.toLowerCase().includes(q) ||
        d.position?.toLowerCase().includes(q) ||
        d.tags?.some((tag) => tag.toLowerCase().includes(q))
    )
  }
  return docs
})

onMounted(async () => {
  await fetchPositions()
  await knowledgeStore.fetchDocs()
})

async function fetchPositions() {
  try {
    const { positions } = await knowledgeApi.getPositions()
    if (positions && positions.length > 0) {
      positionTabs.value = positions
    }
  } catch {
    // keep fallback
  }
}

function handleUploadClick() {
  showAgreement.value = true
}

function handleAgree() {
  showAgreement.value = false
  knowledgeFileInput.value?.click()
}

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

async function deleteKnowledgeDoc(id: number) {
  if (!confirm(t('common.delete') + '?')) return
  knowledgeDeletingId.value = id
  try {
    await knowledgeStore.remove(id)
  } catch (e: any) {
    alert(e.message)
  } finally {
    knowledgeDeletingId.value = null
  }
}
</script>

<template>
  <div class="card space-y-4">
    <h2 class="text-lg font-semibold text-gray-800">{{ t('home.knowledgeMgmt') }}</h2>
    <input ref="knowledgeFileInput" type="file" accept=".md" multiple class="hidden" @change="handleKnowledgeUpload" />
    <button
      @click="handleUploadClick"
      :disabled="uploading"
      class="w-full rounded-xl border-2 border-dashed border-primary-200 px-4 py-6 text-sm text-primary-600 transition hover:border-primary-400 hover:bg-primary-50/50 disabled:opacity-60"
    >
      {{ uploading ? t('common.uploading') : t('home.uploadMd') }}
    </button>

    <!-- Position Tabs + Search + Tags -->
    <div v-if="knowledgeStore.docs.length > 0" class="space-y-3">
      <!-- Search -->
      <div class="relative">
        <input
          v-model="searchQuery"
          :placeholder="t('admin.searchDocs')"
          class="w-full rounded-lg border border-primary-200 bg-white px-3 py-2 pr-8 text-sm min-h-[40px] focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100"
        />
        <button
          v-if="searchQuery"
          @click="searchQuery = ''"
          class="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
        >
          ✕
        </button>
      </div>

      <!-- Position Tabs -->
      <div class="border-b border-gray-200">
        <div class="flex gap-1.5 overflow-x-auto pb-1" style="-ms-overflow-style: none; scrollbar-width: none; -webkit-overflow-scrolling: touch;">
          <button
            @click="activePosition = ALL_TAB"
            class="flex-shrink-0 whitespace-nowrap rounded-lg px-3 py-2 text-sm font-medium transition min-h-[40px]"
            :class="activePosition === ALL_TAB ? 'bg-gradient-brand text-white shadow-soft' : 'bg-primary-50/60 text-gray-700 hover:bg-primary-100'"
          >
            {{ t('admin.all') }} ({{ knowledgeStore.docs.length }})
          </button>
          <button
            v-for="pos in positionTabs"
            :key="pos"
            @click="activePosition = pos"
            class="flex-shrink-0 whitespace-nowrap rounded-lg px-3 py-2 text-sm font-medium transition min-h-[40px]"
            :class="activePosition === pos ? 'bg-gradient-brand text-white shadow-soft' : 'bg-primary-50/60 text-gray-700 hover:bg-primary-100'"
          >
            {{ pos }} ({{ knowledgeStore.docs.filter((d) => d.position === pos).length }})
          </button>
        </div>
      </div>

      <!-- Tag Filter -->
      <div v-if="allTags.length > 0" class="flex flex-wrap gap-1.5">
        <button
          @click="activeTag = ''"
          class="rounded-full border px-2.5 py-1 text-xs transition min-h-[32px]"
          :class="!activeTag ? 'border-primary-400 bg-primary-50 text-primary-700' : 'border-gray-200 text-gray-500 hover:border-primary-300'"
        >
          {{ t('admin.allTags') }}
        </button>
        <button
          v-for="tag in allTags"
          :key="tag"
          @click="activeTag = activeTag === tag ? '' : tag"
          class="rounded-full border px-2.5 py-1 text-xs transition min-h-[32px]"
          :class="activeTag === tag ? 'border-primary-400 bg-primary-50 text-primary-700' : 'border-gray-200 text-gray-500 hover:border-primary-300'"
        >
          {{ tag }}
        </button>
      </div>
    </div>

    <!-- 加载中骨架屏 -->
    <div v-if="knowledgeStore.loading" class="space-y-2">
      <div v-for="i in 4" :key="i" class="h-12 animate-pulse rounded-lg bg-gray-100"></div>
      <div class="text-center text-xs text-gray-400">{{ t('common.loading') }}</div>
    </div>
    <div v-else-if="knowledgeStore.docs.length === 0" class="text-sm text-gray-400">{{ t('home.noDocs') }}</div>
    <div v-else-if="filteredDocs.length === 0" class="text-sm text-gray-400">
      {{ t('admin.noDocsInPosition') }}
    </div>
    <div v-else class="space-y-2">
      <div
        v-for="doc in filteredDocs"
        :key="doc.id"
        :class="['flex items-center justify-between rounded-lg bg-primary-50/50 px-3 py-2', knowledgeDeletingId === doc.id ? 'opacity-50' : '']"
      >
        <div class="min-w-0 flex-1">
          <p class="truncate text-sm font-medium text-gray-700">{{ doc.title || doc.filename }}</p>
          <p class="text-xs text-gray-400">
            {{ doc.position || '-' }} ·
            {{ doc.difficulty || '-' }} ·
            <span :class="{
              'text-yellow-500': doc.status === 'processing',
              'text-green-500': doc.status === 'ready',
              'text-red-500': doc.status === 'failed',
            }">{{ doc.status }}</span>
          </p>
        </div>
        <div class="flex items-center gap-2">
          <button
            @click="showCollaboratorDocId = doc.id"
            class="flex items-center gap-1 text-sm text-purple-500 transition hover:text-purple-700"
            title="协作者"
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
            </svg>
            协作
          </button>
          <button
            @click="showVersionHistoryId = doc.id"
            class="flex items-center gap-1 text-sm text-blue-500 transition hover:text-blue-700"
            title="版本历史"
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            版本
          </button>
          <button
            @click="deleteKnowledgeDoc(doc.id)"
            :disabled="knowledgeDeletingId !== null"
            class="flex items-center gap-1 text-sm text-red-400 transition hover:text-red-600 disabled:opacity-50"
          >
            <span v-if="knowledgeDeletingId === doc.id" class="h-3 w-3 animate-spin rounded-full border-2 border-red-200 border-t-red-500"></span>
            {{ knowledgeDeletingId === doc.id ? t('common.loading') : t('common.delete') }}
          </button>
        </div>
      </div>
    </div>

    <!-- 版本历史弹窗 -->
    <VersionHistory
      v-if="showVersionHistoryId !== null"
      :doc-id="showVersionHistoryId"
      @close="showVersionHistoryId = null"
    />

    <!-- 协作者管理弹窗 -->
    <CollaboratorManager
      v-if="showCollaboratorDocId !== null"
      :doc-id="showCollaboratorDocId"
      @close="showCollaboratorDocId = null"
    />

    <!-- 知识库上传协议弹窗 -->
    <KnowledgeAgreementModal
      :visible="showAgreement"
      @close="showAgreement = false"
      @agree="handleAgree"
    />
  </div>
</template>
