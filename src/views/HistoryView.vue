<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  getInterviewHistory,
  deleteInterview,
  batchDeleteInterviews,
} from '@/api/interview'
import type { InterviewRecord } from '@/types'

const { t } = useI18n()
const router = useRouter()
const records = ref<InterviewRecord[]>([])
const loading = ref(true)
const selectedIds = ref<Set<number>>(new Set())
const deleting = ref(false)

const allSelected = computed(
  () => records.value.length > 0 && selectedIds.value.size === records.value.length,
)

onMounted(async () => {
  await fetchRecords()
})

async function fetchRecords() {
  loading.value = true
  try {
    records.value = await getInterviewHistory()
    selectedIds.value = new Set()
  } finally {
    loading.value = false
  }
}

function toggleSelect(id: number) {
  if (selectedIds.value.has(id)) {
    selectedIds.value.delete(id)
  } else {
    selectedIds.value.add(id)
  }
  selectedIds.value = new Set(selectedIds.value)
}

function toggleSelectAll() {
  if (allSelected.value) {
    selectedIds.value = new Set()
  } else {
    selectedIds.value = new Set(records.value.map((r) => r.id))
  }
}

async function handleDelete(id: number) {
  if (!confirm(t('history.confirmDelete'))) return
  deleting.value = true
  try {
    await deleteInterview(id)
    await fetchRecords()
  } catch (e: any) {
    alert(t('history.deleteFailed') + e.message)
  } finally {
    deleting.value = false
  }
}

async function handleBatchDelete() {
  if (selectedIds.value.size === 0) return
  if (!confirm(t('history.confirmBatchDelete', { count: selectedIds.value.size }))) return
  deleting.value = true
  try {
    await batchDeleteInterviews(Array.from(selectedIds.value))
    await fetchRecords()
  } catch (e: any) {
    alert(t('history.deleteFailed') + e.message)
  } finally {
    deleting.value = false
  }
}
</script>

<template>
  <div class="mx-auto max-w-3xl px-4 py-10">
      <div class="mb-6 flex items-center justify-between">
        <h1 class="text-2xl font-bold text-gray-900">{{ t('history.title') }}</h1>
        <button
          v-if="selectedIds.size > 0"
          @click="handleBatchDelete"
          :disabled="deleting"
          class="rounded-lg bg-red-500 px-4 py-2 text-sm text-white hover:bg-red-600 disabled:opacity-50"
        >
          {{ t('history.deleteSelected') }} ({{ selectedIds.size }})
        </button>
      </div>

      <div v-if="loading" class="py-20 text-center text-gray-400">{{ t('common.loading') }}</div>
      <div v-else-if="records.length === 0" class="py-20 text-center text-gray-400">
        {{ t('history.noRecords') }}
      </div>
      <div v-else>
        <div class="mb-3 flex items-center gap-2">
          <input
            type="checkbox"
            :checked="allSelected"
            @change="toggleSelectAll"
            class="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
          />
          <span class="text-sm text-gray-500">{{ t('history.selectAll') }}</span>
        </div>

        <div class="space-y-3">
          <div
            v-for="record in records"
            :key="record.id"
            class="flex items-center gap-3 rounded-lg bg-white p-4 shadow-sm hover:shadow-md transition"
          >
            <input
              type="checkbox"
              :checked="selectedIds.has(record.id)"
              @change="toggleSelect(record.id)"
              @click.stop
              class="h-4 w-4 flex-shrink-0 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
            />

            <div
              class="flex flex-1 cursor-pointer items-center justify-between"
              @click="router.push(`/report/${record.id}`)"
            >
              <div>
                <p class="font-medium text-gray-800">
                  {{ t('positions.' + record.position, record.position) }} ·
                  {{ t('difficulty.' + record.difficulty, record.difficulty) }}
                </p>
                <p class="text-xs text-gray-400">
                  {{ record.startedAt }}
                  <span v-if="record.endedAt"> → {{ record.endedAt }}</span>
                </p>
              </div>
              <div class="flex items-center gap-2">
                <!-- 回放入口 -->
                <button
                  @click.stop="router.push(`/interview/${record.id}/playback`)"
                  class="rounded-lg border border-gray-300 px-2.5 py-1 text-xs text-gray-600 hover:bg-gray-50"
                >
                  <svg viewBox="0 0 24 24" class="mr-1 inline h-3.5 w-3.5" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
                  回放
                </button>
                <span class="text-sm text-gray-500">{{ record.duration }} {{ t('history.minutes') }}</span>
                <span
                  :class="[
                    'rounded-full px-2 py-1 text-xs',
                    record.status === '已结束'
                      ? 'bg-green-100 text-green-700'
                      : 'bg-yellow-100 text-yellow-700',
                  ]"
                >
                  {{ record.status === '已结束' ? t('history.completed') : t('history.inProgress') }}
                </span>
                <button
                  @click.stop="handleDelete(record.id)"
                  :disabled="deleting"
                  class="text-sm text-red-400 hover:text-red-600 disabled:opacity-50"
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
