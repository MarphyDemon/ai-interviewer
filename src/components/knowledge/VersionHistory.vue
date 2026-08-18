<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useKnowledgeStore } from '@/stores/knowledge'
import type { KnowledgeVersionDetail } from '@/types'

const props = defineProps<{ docId: number }>()
const emit = defineEmits<{ close: [] }>()

const knowledgeStore = useKnowledgeStore()
const showCreateModal = ref(false)
const changeNote = ref('')
const previewVersion = ref<KnowledgeVersionDetail | null>(null)

async function loadVersions() {
  await knowledgeStore.fetchVersions(props.docId)
}

async function handleCreateVersion() {
  if (!changeNote.value.trim()) return
  await knowledgeStore.createVersion(props.docId, changeNote.value.trim())
  changeNote.value = ''
  showCreateModal.value = false
}

async function handleRollback(versionId: number, versionNumber: number) {
  if (!confirm(`确定回滚到版本 v${versionNumber}？当前状态将被保存为新版本。`)) return
  await knowledgeStore.rollbackVersion(props.docId, versionId)
}

async function handlePreview(versionId: number) {
  const detail = await knowledgeStore.fetchVersion(props.docId, versionId)
  previewVersion.value = detail
}

async function handleDelete(versionId: number) {
  if (!confirm('确定删除此版本？')) return
  await knowledgeStore.deleteVersion(props.docId, versionId)
}

function formatDate(dateStr: string) {
  return new Date(dateStr).toLocaleString('zh-CN')
}

onMounted(loadVersions)
</script>

<template>
  <div class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
    @click.self="emit('close')">
    <div class="bg-white rounded-xl w-full max-w-2xl max-h-[85vh] mx-4 flex flex-col">
      <!-- Header -->
      <div class="flex items-center justify-between px-5 py-4 border-b border-gray-200">
        <h2 class="text-lg font-semibold text-gray-900">版本历史</h2>
        <div class="flex gap-2">
          <button @click="showCreateModal = true"
            class="px-3 py-1.5 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700">
            + 保存版本
          </button>
          <button @click="emit('close')" class="p-1 text-gray-400 hover:text-gray-600">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      <!-- Version list -->
      <div class="flex-1 overflow-y-auto p-5">
        <div v-if="knowledgeStore.versions.length === 0" class="text-center py-8 text-gray-500">
          暂无版本记录
        </div>
        <div v-else class="space-y-3">
          <div v-for="v in knowledgeStore.versions" :key="v.id"
            class="border border-gray-200 rounded-lg p-4 hover:border-gray-300 transition-colors">
            <div class="flex items-center justify-between">
              <div>
                <div class="flex items-center gap-2">
                  <span class="text-sm font-semibold text-gray-900">v{{ v.versionNumber }}</span>
                  <span class="px-2 py-0.5 bg-gray-100 text-gray-600 text-xs rounded-full">
                    {{ v.title || '无标题' }}
                  </span>
                </div>
                <p class="text-sm text-gray-600 mt-1">{{ v.changeNote || '无变更说明' }}</p>
                <p class="text-xs text-gray-400 mt-1">{{ formatDate(v.createdAt) }}</p>
              </div>
              <div class="flex gap-1">
                <button @click="handlePreview(v.id)"
                  class="px-2 py-1 text-xs text-gray-600 hover:bg-gray-100 rounded">
                  查看
                </button>
                <button @click="handleRollback(v.id, v.versionNumber)"
                  class="px-2 py-1 text-xs text-blue-600 hover:bg-blue-50 rounded">
                  回滚
                </button>
                <button @click="handleDelete(v.id)"
                  class="px-2 py-1 text-xs text-red-600 hover:bg-red-50 rounded">
                  删除
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Create version modal -->
      <div v-if="showCreateModal" class="fixed inset-0 bg-black bg-opacity-30 flex items-center justify-center z-10">
        <div class="bg-white rounded-lg p-5 w-full max-w-sm mx-4">
          <h3 class="text-base font-semibold text-gray-900 mb-3">保存新版本</h3>
          <textarea v-model="changeNote" placeholder="描述这个版本的变更（可选）"
            class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm h-24 resize-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
          <div class="flex gap-2 justify-end mt-4">
            <button @click="showCreateModal = false"
              class="px-4 py-1.5 text-sm text-gray-600 hover:bg-gray-100 rounded-lg">
              取消
            </button>
            <button @click="handleCreateVersion"
              class="px-4 py-1.5 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700">
              保存
            </button>
          </div>
        </div>
      </div>

      <!-- Preview modal -->
      <div v-if="previewVersion" class="fixed inset-0 bg-black bg-opacity-30 flex items-center justify-center z-10">
        <div class="bg-white rounded-lg p-5 w-full max-w-lg mx-4 max-h-[60vh] flex flex-col">
          <div class="flex items-center justify-between mb-3">
            <h3 class="text-base font-semibold text-gray-900">
              v{{ previewVersion.versionNumber }} - {{ previewVersion.title }}
            </h3>
            <button @click="previewVersion = null" class="text-gray-400 hover:text-gray-600">
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          <div class="flex-1 overflow-y-auto">
            <pre class="text-sm text-gray-700 whitespace-pre-wrap font-mono bg-gray-50 p-3 rounded">{{ previewVersion.content }}</pre>
          </div>
          <div class="flex gap-2 justify-end mt-4">
            <button @click="previewVersion = null"
              class="px-4 py-1.5 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700">
              关闭
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>