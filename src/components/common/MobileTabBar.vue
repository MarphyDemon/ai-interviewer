<script setup lang="ts">
import { useRouter, useRoute } from 'vue-router'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const tabs = [
  { path: '/', label: '首页', icon: '🏠' },
  { path: '/chat', label: '聊天', icon: '🤖' },
  { path: '/setup', label: '面试', icon: '💬' },
  { path: '/history', label: '历史', icon: '📋' },
  { path: userStore.isLoggedIn ? '/profile' : '/login', label: userStore.isLoggedIn ? '我的' : '登录', icon: '👤' },
]

const navigate = (path: string) => {
  router.push(path)
}
</script>

<template>
  <nav
    class="fixed bottom-0 left-0 right-0 z-50 bg-white/95 backdrop-blur border-t border-gray-200
           flex justify-around items-center shadow-[0_-2px_10px_rgba(0,0,0,0.05)]"
    style="padding-bottom: env(safe-area-inset-bottom); min-height: 56px;"
  >
    <button
      v-for="tab in tabs"
      :key="tab.path"
      @click="navigate(tab.path)"
      class="flex flex-col items-center justify-center flex-1 py-2 transition-colors
             text-gray-500 active:text-indigo-600"
      :class="{ 'text-indigo-600': route.path === tab.path }"
    >
      <span class="text-xl leading-none">{{ tab.icon }}</span>
      <span class="text-xs mt-0.5">{{ tab.label }}</span>
    </button>
  </nav>
</template>