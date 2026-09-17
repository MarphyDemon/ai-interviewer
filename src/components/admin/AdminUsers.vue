<script setup lang="ts">
import { onMounted, ref } from 'vue'
import * as adminApi from '@/api/admin'

const users = ref<adminApi.UserListItem[]>([])
const usersLoading = ref(false)
const showQuotaModal = ref(false)
const quotaUserId = ref<number | null>(null)
const quotaData = ref<{
  plan: string
  interview_limit: number
  interview_used: number
  knowledge_limit: number
  knowledge_used: number
  ai_calls_limit: number
  ai_calls_used: number
}>({
  plan: 'free',
  interview_limit: 10,
  interview_used: 0,
  knowledge_limit: 20,
  knowledge_used: 0,
  ai_calls_limit: 100,
  ai_calls_used: 0,
})

onMounted(() => {
  fetchUsers()
})

async function fetchUsers() {
  usersLoading.value = true
  try {
    users.value = await adminApi.getUsers()
  } catch {
    // 401 由 client.ts 统一派发 admin-unauthorized，AdminView 会回退到口令校验界面
    users.value = []
  } finally {
    usersLoading.value = false
  }
}

async function promoteUser(userId: number, role: string) {
  if (!confirm(`确定将该用户角色修改为 ${role === 'admin' ? '管理员' : '普通用户'}？`)) return
  try {
    await adminApi.promoteUser(userId, role)
    await fetchUsers()
  } catch (e: any) {
    alert(e.message)
  }
}

function openQuotaModal(user: adminApi.UserListItem) {
  quotaUserId.value = user.id
  quotaData.value = {
    plan: user.plan || 'free',
    interview_limit: 10,
    interview_used: 0,
    knowledge_limit: 20,
    knowledge_used: 0,
    ai_calls_limit: 100,
    ai_calls_used: 0,
  }
  showQuotaModal.value = true
}

async function saveQuota() {
  if (quotaUserId.value === null) return
  try {
    await adminApi.setUserQuota(quotaUserId.value, {
      plan: quotaData.value.plan,
      interviewLimit: quotaData.value.interview_limit,
      knowledgeLimit: quotaData.value.knowledge_limit,
      aiCallsLimit: quotaData.value.ai_calls_limit,
    })
    showQuotaModal.value = false
    await fetchUsers()
  } catch (e: any) {
    alert(e.message)
  }
}
</script>

<template>
  <div class="card space-y-4">
    <h2 class="text-lg font-semibold text-gray-800">👥 用户管理</h2>

    <div v-if="usersLoading" class="py-8 text-center text-gray-400">加载中...</div>
    <div v-else-if="users.length === 0" class="py-8 text-center text-sm text-gray-400">暂无用户</div>
    <div v-else class="space-y-3">
      <div
        v-for="user in users"
        :key="user.id"
        class="rounded-xl bg-primary-50/50 p-4"
      >
        <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2">
              <span class="font-medium text-gray-800">{{ user.username }}</span>
              <span
                class="rounded-full px-2 py-0.5 text-xs"
                :class="user.role === 'admin' ? 'bg-purple-100 text-purple-700' : 'bg-gray-200 text-gray-600'"
              >
                {{ user.role === 'admin' ? '管理员' : '普通用户' }}
              </span>
              <span
                class="rounded-full px-2 py-0.5 text-xs"
                :class="{
                  'bg-green-100 text-green-700': user.plan === 'free',
                  'bg-blue-100 text-blue-700': user.plan === 'standard',
                  'bg-purple-100 text-purple-700': user.plan === 'enterprise',
                }"
              >
                {{ user.plan === 'free' ? '免费版' : user.plan === 'standard' ? '标准版' : '企业版' }}
              </span>
            </div>
            <div class="mt-1 text-xs text-gray-500">
              ID: {{ user.id }} · 注册: {{ new Date(user.createdAt).toLocaleDateString() }}
            </div>
          </div>
          <div class="flex flex-wrap items-center gap-2">
            <button
              @click="openQuotaModal(user)"
              class="rounded-lg bg-blue-50 px-3 py-1.5 text-xs text-blue-600 transition hover:bg-blue-100"
            >
              设置配额
            </button>
            <button
              v-if="user.role === 'admin'"
              @click="promoteUser(user.id, 'user')"
              class="rounded-lg bg-amber-50 px-3 py-1.5 text-xs text-amber-600 transition hover:bg-amber-100"
            >
              降级为普通用户
            </button>
            <button
              v-else
              @click="promoteUser(user.id, 'admin')"
              class="rounded-lg bg-gradient-brand px-3 py-1.5 text-xs text-white transition hover:brightness-110"
            >
              提升为管理员
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 配额设置弹窗 -->
    <div v-if="showQuotaModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" @click.self="showQuotaModal = false">
      <div class="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
        <h3 class="mb-4 text-lg font-semibold text-gray-800">设置用户配额</h3>
        <div class="space-y-4">
          <div>
            <label class="mb-1 block text-sm font-medium text-gray-700">套餐</label>
            <select v-model="quotaData.plan" class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100">
              <option value="free">免费版</option>
              <option value="standard">标准版</option>
              <option value="enterprise">企业版</option>
            </select>
          </div>
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="mb-1 block text-sm font-medium text-gray-700">面试次数限制</label>
              <input v-model.number="quotaData.interview_limit" type="number" min="0" class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100" />
            </div>
            <div>
              <label class="mb-1 block text-sm font-medium text-gray-700">已用面试次数</label>
              <input v-model.number="quotaData.interview_used" type="number" min="0" class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100" />
            </div>
            <div>
              <label class="mb-1 block text-sm font-medium text-gray-700">知识库文档限制</label>
              <input v-model.number="quotaData.knowledge_limit" type="number" min="0" class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100" />
            </div>
            <div>
              <label class="mb-1 block text-sm font-medium text-gray-700">已用知识库文档</label>
              <input v-model.number="quotaData.knowledge_used" type="number" min="0" class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100" />
            </div>
            <div>
              <label class="mb-1 block text-sm font-medium text-gray-700">AI 调用限制</label>
              <input v-model.number="quotaData.ai_calls_limit" type="number" min="0" class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100" />
            </div>
            <div>
              <label class="mb-1 block text-sm font-medium text-gray-700">已用 AI 调用</label>
              <input v-model.number="quotaData.ai_calls_used" type="number" min="0" class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100" />
            </div>
          </div>
        </div>
        <div class="mt-6 flex gap-3">
          <button @click="showQuotaModal = false" class="flex-1 rounded-lg border border-gray-300 px-4 py-2 text-sm text-gray-700 transition hover:bg-gray-50">
            取消
          </button>
          <button @click="saveQuota" class="flex-1 rounded-lg bg-gradient-brand px-4 py-2 text-sm text-white transition hover:brightness-110">
            保存
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
