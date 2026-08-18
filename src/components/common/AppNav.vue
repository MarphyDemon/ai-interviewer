<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import LangToggle from './LangToggle.vue'
import NotificationCenter from './NotificationCenter.vue'
import { useUserStore } from '@/stores/user'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const links = computed(() => {
  const list = [
    { name: 'home', to: '/', label: t('nav.home') },
    { name: 'chat', to: '/chat', label: t('nav.chat') },
    { name: 'code', to: '/code', label: t('nav.codePractice') },
    { name: 'history', to: '/history', label: t('nav.history') },
  ]
  if (userStore.isAdmin) {
    list.push({ name: 'admin', to: '/admin', label: t('nav.admin') })
  }
  return list
})

const mobileLinks = computed(() => links.value.filter(l => l.name !== 'code'))

function isActive(to: string) {
  if (to === '/') return route.path === '/'
  return route.path.startsWith(to)
}

function logout() {
  userStore.logout()
  router.push('/')
}
</script>

<template>
  <header class="sticky top-0 z-40 border-b border-primary-100/60 bg-white/80 backdrop-blur-lg">
    <div class="mx-auto flex h-16 max-w-6xl items-center justify-between px-4">
      <router-link to="/" class="flex items-center gap-2">
        <span class="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-brand text-white shadow-soft">
          <svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4" />
          </svg>
        </span>
        <span class="text-lg font-bold text-gradient">{{ t('nav.brand') }}</span>
      </router-link>

      <nav class="hidden items-center gap-1 md:flex">
        <router-link
          v-for="link in links"
          :key="link.name"
          :to="link.to"
          class="rounded-lg px-3 py-2 text-sm font-medium transition"
          :class="
            isActive(link.to)
              ? 'bg-primary-50 text-primary-700'
              : 'text-gray-600 hover:bg-primary-50/60 hover:text-primary-700'
          "
        >
          {{ link.label }}
        </router-link>
      </nav>

      <div class="flex items-center gap-2">
        <template v-if="userStore.isLoggedIn">
          <span class="hidden text-sm text-gray-600 sm:inline">{{ userStore.user?.username }}</span>
          <NotificationCenter />
          <router-link to="/settings" class="btn-ghost !px-3 !py-2 text-sm" title="设置">
            <svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="3" />
              <path stroke-linecap="round" stroke-linejoin="round" d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09a1.65 1.65 0 00-1-1.51 1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09a1.65 1.65 0 001.51-1 1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 010-2.83 2 2 0 012.83 0l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 0 2 2 0 010 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z" />
            </svg>
          </router-link>
          <button class="btn-ghost !px-3 !py-2 text-sm" @click="logout">{{ t('nav.logout') }}</button>
        </template>
        <template v-else>
          <button class="btn-ghost !px-3 !py-2 text-sm" @click="router.push('/login')">{{ t('nav.login') }}</button>
          <button class="btn-ghost !px-3 !py-2 text-sm" @click="router.push('/register')">{{ t('nav.register') }}</button>
        </template>
        <button
          class="btn-primary !px-4 !py-2 text-sm"
          @click="router.push('/setup')"
        >
          {{ t('nav.startInterview') }}
        </button>
        <LangToggle />
      </div>
    </div>

    <!-- 移动端导航（不包含代码练习） -->
    <nav class="flex items-center gap-1 overflow-x-auto border-t border-primary-100/60 px-4 py-2 md:hidden">
      <router-link
        v-for="link in mobileLinks"
        :key="link.name"
        :to="link.to"
        class="whitespace-nowrap rounded-lg px-3 py-1.5 text-sm font-medium transition"
        :class="
          isActive(link.to)
            ? 'bg-primary-50 text-primary-700'
            : 'text-gray-600 hover:bg-primary-50/60 hover:text-primary-700'
        "
      >
        {{ link.label }}
      </router-link>
    </nav>
  </header>
</template>
