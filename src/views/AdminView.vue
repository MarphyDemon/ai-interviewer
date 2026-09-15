<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import * as adminApi from '@/api/admin'
import { useUserStore } from '@/stores/user'
import AdminKnowledge from '@/components/admin/AdminKnowledge.vue'
import AdminLlmConfig from '@/components/admin/AdminLlmConfig.vue'
import AdminAvatarConfig from '@/components/admin/AdminAvatarConfig.vue'
import AdminUsers from '@/components/admin/AdminUsers.vue'
import AdminStats from '@/components/admin/AdminStats.vue'

const { t } = useI18n()
const userStore = useUserStore()

const verified = ref(false)
const password = ref('')
const activeTab = ref<'knowledge' | 'llm' | 'avatar' | 'users' | 'stats'>('knowledge')

onMounted(async () => {
  const token = localStorage.getItem('admin_token')
  const isAdmin = userStore.isAdmin
  if (!token && !isAdmin) return
  verified.value = true
})

async function verify() {
  try {
    const res = await adminApi.verifyAdmin(password.value)
    localStorage.setItem('admin_token', res.token)
    verified.value = true
  } catch {
    alert(t('admin.wrongPassword'))
  }
}
</script>

<template>
  <div class="mx-auto max-w-2xl px-4 py-10">
    <h1 class="mb-8 text-2xl font-bold text-gray-900">{{ t('admin.title') }}</h1>

    <!-- 口令校验 -->
    <div v-if="!verified" class="card">
      <p class="mb-4 text-gray-600">{{ t('admin.enterPassword') }}</p>
      <div class="flex gap-2">
        <input
          v-model="password"
          type="password"
          @keydown.enter="verify"
          :placeholder="t('admin.password')"
          class="flex-1 rounded-lg border border-primary-200 bg-white px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100"
        />
        <button @click="verify" class="btn-primary !px-5 !py-2 text-sm">
          {{ t('common.confirm') }}
        </button>
      </div>
    </div>

    <div v-else class="space-y-6">
      <!-- Tab 导航 -->
      <div class="flex gap-1 rounded-xl bg-gray-100 p-1 overflow-x-auto" style="-ms-overflow-style: none; scrollbar-width: none;">
        <button
          @click="activeTab = 'knowledge'"
          class="flex-shrink-0 flex-1 whitespace-nowrap rounded-lg px-3 py-2 text-sm font-medium transition min-h-[40px]"
          :class="activeTab === 'knowledge' ? 'bg-white text-primary-600 shadow-sm' : 'text-gray-600 hover:text-gray-900'"
        >
          📚 知识库
        </button>
        <button
          @click="activeTab = 'llm'"
          class="flex-shrink-0 flex-1 whitespace-nowrap rounded-lg px-3 py-2 text-sm font-medium transition min-h-[40px]"
          :class="activeTab === 'llm' ? 'bg-white text-primary-600 shadow-sm' : 'text-gray-600 hover:text-gray-900'"
        >
          🤖 LLM 配置
        </button>
        <button
          @click="activeTab = 'avatar'"
          class="flex-shrink-0 flex-1 whitespace-nowrap rounded-lg px-3 py-2 text-sm font-medium transition min-h-[40px]"
          :class="activeTab === 'avatar' ? 'bg-white text-primary-600 shadow-sm' : 'text-gray-600 hover:text-gray-900'"
        >
          👤 具身交互智能体
        </button>
        <button
          @click="activeTab = 'users'"
          class="flex-shrink-0 flex-1 whitespace-nowrap rounded-lg px-3 py-2 text-sm font-medium transition min-h-[40px]"
          :class="activeTab === 'users' ? 'bg-white text-primary-600 shadow-sm' : 'text-gray-600 hover:text-gray-900'"
        >
          👥 用户管理
        </button>
        <button
          @click="activeTab = 'stats'"
          class="flex-shrink-0 flex-1 whitespace-nowrap rounded-lg px-3 py-2 text-sm font-medium transition min-h-[40px]"
          :class="activeTab === 'stats' ? 'bg-white text-primary-600 shadow-sm' : 'text-gray-600 hover:text-gray-900'"
        >
          📊 数据看板
        </button>
      </div>

      <!-- Tab 内容 -->
      <AdminKnowledge v-if="activeTab === 'knowledge'" />
      <AdminLlmConfig v-else-if="activeTab === 'llm'" />
      <AdminAvatarConfig v-else-if="activeTab === 'avatar'" />
      <AdminUsers v-else-if="activeTab === 'users'" />
      <AdminStats v-else-if="activeTab === 'stats'" />
    </div>
  </div>
</template>
