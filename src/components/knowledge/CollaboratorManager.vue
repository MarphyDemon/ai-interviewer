<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useKnowledgeStore } from '@/stores/knowledge'

const props = defineProps<{ docId: number }>()
const emit = defineEmits<{ close: [] }>()

const knowledgeStore = useKnowledgeStore()
const showAddModal = ref(false)
const newUserId = ref<number | null>(null)
const newPermission = ref<'read' | 'edit' | 'admin'>('edit')

async function loadCollaborators() {
  await knowledgeStore.fetchCollaborators(props.docId)
}

async function handleAdd() {
  if (!newUserId.value) return
  await knowledgeStore.addCollaborator(props.docId, newUserId.value, newPermission.value)
  newUserId.value = null
  newPermission.value = 'edit'
  showAddModal.value = false
}

async function handleRemove(collabId: number) {
  if (!confirm('确定移除该协作者？')) return
  await knowledgeStore.removeCollaborator(props.docId, collabId)
}

function permissionLabel(p: string) {
  return { read: '只读', edit: '可编辑', admin: '管理员' }[p] || p
}

function permissionClass(p: string) {
  return {
    read: 'bg-gray-100 text-gray-600',
    edit: 'bg-blue-100 text-blue-600',
    admin: 'bg-purple-100 text-purple-600',
  }[p] || 'bg-gray-100 text-gray-600'
}

onMounted(loadCollaborators)
</script>

<template>
  <div class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
    @click.self="emit('close')">
    <div class="bg-white rounded-xl w-full max-w-lg max-h-[85vh] mx-4 flex flex-col">
      <div class="flex items-center justify-between px-5 py-4 border-b border-gray-200">
        <h2 class="text-lg font-semibold text-gray-900">协作者管理</h2>
        <div class="flex gap-2">
          <button @click="showAddModal = true"
            class="px-3 py-1.5 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700">
            + 添加协作者
          </button>
          <button @click="emit('close')" class="p-1 text-gray-400 hover:text-gray-600">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      <div class="flex-1 overflow-y-auto p-5">
        <div v-if="knowledgeStore.collaborators.length === 0" class="text-center py-8 text-gray-500">
          暂无协作者
        </div>
        <div v-else class="space-y-2">
          <div v-for="c in knowledgeStore.collaborators" :key="c.id"
            class="flex items-center justify-between border border-gray-200 rounded-lg p-3">
            <div class="flex items-center gap-3">
              <div class="w-8 h-8 bg-gradient-brand rounded-full flex items-center justify-center text-white text-sm font-medium">
                {{ c.username?.[0]?.toUpperCase() || 'U' }}
              </div>
              <div>
                <p class="text-sm font-medium text-gray-900">{{ c.username || `用户#${c.userId}` }}</p>
                <span :class="['text-xs px-2 py-0.5 rounded-full', permissionClass(c.permission)]">
                  {{ permissionLabel(c.permission) }}
                </span>
              </div>
            </div>
            <button @click="handleRemove(c.id)"
              class="text-xs text-red-500 hover:text-red-700">
              移除
            </button>
          </div>
        </div>
      </div>

      <!-- Add modal -->
      <div v-if="showAddModal" class="fixed inset-0 bg-black bg-opacity-30 flex items-center justify-center z-10">
        <div class="bg-white rounded-lg p-5 w-full max-w-sm mx-4">
          <h3 class="text-base font-semibold text-gray-900 mb-3">添加协作者</h3>
          <div class="space-y-3">
            <div>
              <label class="text-sm text-gray-700 block mb-1">用户 ID</label>
              <input v-model.number="newUserId" type="number" placeholder="输入用户 ID"
                class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
            </div>
            <div>
              <label class="text-sm text-gray-700 block mb-1">权限</label>
              <select v-model="newPermission"
                class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
                <option value="read">只读</option>
                <option value="edit">可编辑</option>
                <option value="admin">管理员</option>
              </select>
            </div>
          </div>
          <div class="flex gap-2 justify-end mt-4">
            <button @click="showAddModal = false"
              class="px-4 py-1.5 text-sm text-gray-600 hover:bg-gray-100 rounded-lg">
              取消
            </button>
            <button @click="handleAdd"
              class="px-4 py-1.5 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700">
              添加
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>