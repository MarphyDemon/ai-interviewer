<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import LangToggle from './LangToggle.vue'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

const links = computed(() => [
  { name: 'home', to: '/', label: t('nav.home') },
  { name: 'chat', to: '/chat', label: t('nav.chat') },
  { name: 'history', to: '/history', label: t('nav.history') },
  { name: 'admin', to: '/admin', label: t('nav.admin') },
])

function isActive(to: string) {
  if (to === '/') return route.path === '/'
  return route.path.startsWith(to)
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
        <button
          class="btn-primary !px-4 !py-2 text-sm"
          @click="router.push('/setup')"
        >
          {{ t('nav.startInterview') }}
        </button>
        <LangToggle />
      </div>
    </div>

    <!-- 移动端导航 -->
    <nav class="flex items-center gap-1 overflow-x-auto border-t border-primary-100/60 px-4 py-2 md:hidden">
      <router-link
        v-for="link in links"
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
