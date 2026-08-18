<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const isOpen = ref(false)

function toggle() {
  isOpen.value = !isOpen.value
  if (isOpen.value && userStore.notifications.length === 0) {
    userStore.fetchNotifications()
  }
}

function formatTime(dateStr: string) {
  const d = new Date(dateStr)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return '刚刚'
  if (mins < 60) return `${mins} 分钟前`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours} 小时前`
  return d.toLocaleDateString('zh-CN')
}

function typeIcon(type: string) {
  switch (type) {
    case 'collaboration': return '🤝'
    case 'review': return '✅'
    case 'system': return '🔔'
    default: return '📌'
  }
}

onMounted(() => {
  if (userStore.isLoggedIn) {
    userStore.fetchNotifications()
  }
})
</script>

<template>
  <div class="relative">
    <button
      @click="toggle"
      class="relative p-2 text-gray-600 hover:bg-gray-100 rounded-lg transition"
    >
      <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
          d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
      </svg>
      <span v-if="userStore.unreadCount > 0"
        class="absolute -top-0.5 -right-0.5 w-5 h-5 bg-red-500 text-white text-xs rounded-full flex items-center justify-center">
        {{ userStore.unreadCount > 9 ? '9+' : userStore.unreadCount }}
      </span>
    </button>

    <div v-if="isOpen" class="fixed inset-0 z-40" @click="isOpen = false"></div>

    <div v-if="isOpen"
      class="absolute right-0 mt-2 w-80 bg-white rounded-xl shadow-lg border border-gray-200 z-50 overflow-hidden">
      <div class="flex items-center justify-between px-4 py-3 border-b border-gray-100">
        <h3 class="text-sm font-semibold text-gray-900">通知</h3>
        <button v-if="userStore.unreadCount > 0"
          @click="userStore.markAllRead()"
          class="text-xs text-blue-600 hover:text-blue-800">
          全部已读
        </button>
      </div>
      <div class="max-h-80 overflow-y-auto">
        <div v-if="userStore.notifications.length === 0" class="py-8 text-center text-gray-400 text-sm">
          暂无通知
        </div>
        <div v-else>
          <div v-for="n in userStore.notifications" :key="n.id"
            @click="!n.isRead && userStore.markNotificationRead(n.id)"
            :class="[
              'px-4 py-3 border-b border-gray-50 cursor-pointer hover:bg-gray-50 transition',
              !n.isRead ? 'bg-blue-50/30' : '',
            ]">
            <div class="flex items-start gap-2">
              <span class="text-base">{{ typeIcon(n.type) }}</span>
              <div class="flex-1 min-w-0">
                <p class="text-sm text-gray-900 font-medium truncate">{{ n.title }}</p>
                <p class="text-xs text-gray-600 line-clamp-2 mt-0.5">{{ n.content }}</p>
                <p class="text-xs text-gray-400 mt-1">{{ formatTime(n.createdAt) }}</p>
              </div>
              <span v-if="!n.isRead" class="w-2 h-2 bg-blue-500 rounded-full mt-1.5 flex-shrink-0"></span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>