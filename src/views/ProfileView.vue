<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useUserStore } from '@/stores/user'
import { getInterviewHistory } from '@/api/interview'
import { getProfileSummary } from '@/api/profile'
import type { ProfileSummary } from '@/types'
import { shareContent, detectHost } from '@/utils/bridge'

const { t } = useI18n()
const router = useRouter()
const userStore = useUserStore()

const host = detectHost()

const stats = ref({
  totalInterviews: 0,
  completedInterviews: 0,
})
const loadingStats = ref(true)

/** 跨会话面试画像（弱点记忆） */
const profile = ref<ProfileSummary | null>(null)
const loadingProfile = ref(true)

onMounted(async () => {
  await userStore.fetchMe()
  await Promise.all([fetchStats(), fetchProfile()])
})

async function fetchProfile() {
  loadingProfile.value = true
  try {
    profile.value = await getProfileSummary(6)
  } catch {
    // 画像属增强信息，失败静默
  } finally {
    loadingProfile.value = false
  }
}

async function fetchStats() {
  loadingStats.value = true
  try {
    const records = await getInterviewHistory()
    stats.value.totalInterviews = records.length
    stats.value.completedInterviews = records.filter(r => r.status === '已结束').length
  } catch {
    // ignore
  } finally {
    loadingStats.value = false
  }
}

async function handleShare() {
  const url = window.location.origin
  await shareContent({
    title: 'AI 面试官',
    text: '快来和具身交互智能体面试官一起练习面试！',
    url,
  })
}

async function handleLogout() {
  if (!confirm(t('profile.confirmLogout'))) return
  userStore.logout()
  router.push('/login')
}

function navigate(path: string) {
  router.push(path)
}

const menuSections = computed(() => [
  {
    title: t('profile.learn.title'),
    items: [
      {
        icon: '📋',
        label: t('profile.learn.history'),
        desc: t('profile.learn.historyDesc'),
        path: '/history',
      },
      {
        icon: '💬',
        label: t('profile.learn.chat'),
        desc: t('profile.learn.chatDesc'),
        path: '/chat',
      },
      {
        icon: '🎯',
        label: t('profile.learn.setup'),
        desc: t('profile.learn.setupDesc'),
        path: '/setup',
      },
    ],
  },
  {
    title: t('profile.settings.title'),
    items: [
      {
        icon: '⚙️',
        label: t('profile.settings.admin'),
        desc: t('profile.settings.adminDesc'),
        path: '/admin',
      },
    ],
  },
])
</script>

<template>
  <div class="min-h-screen bg-gray-50 pb-20">
    <!-- User Header -->
    <div class="bg-gradient-brand px-4 pb-6 pt-8 text-white">
      <div class="flex items-center gap-4">
        <div class="flex h-16 w-16 items-center justify-center rounded-full bg-white/20 text-3xl backdrop-blur">
          👤
        </div>
        <div class="flex-1 min-w-0">
          <h2 class="text-xl font-bold truncate">
            {{ userStore.user?.username || t('profile.defaultName') }}
          </h2>
          <p class="text-sm text-white/80">
            {{ host === 'capacitor' ? 'App' : host === 'miniprogram' ? '小程序' : 'Web' }}
          </p>
        </div>
        <button
          @click="handleLogout"
          class="rounded-lg bg-white/20 px-4 py-2 text-sm font-medium backdrop-blur transition hover:bg-white/30"
        >
          {{ t('profile.logout') }}
        </button>
      </div>

      <!-- Quick Stats -->
      <div class="mt-6 grid grid-cols-2 gap-3">
        <div class="rounded-xl bg-white/15 px-4 py-3 backdrop-blur">
          <p class="text-2xl font-bold">
            {{ loadingStats ? '-' : stats.totalInterviews }}
          </p>
          <p class="text-xs text-white/70">{{ t('profile.stats.totalInterviews') }}</p>
        </div>
        <div class="rounded-xl bg-white/15 px-4 py-3 backdrop-blur">
          <p class="text-2xl font-bold">
            {{ loadingStats ? '-' : stats.completedInterviews }}
          </p>
          <p class="text-xs text-white/70">{{ t('profile.stats.completedInterviews') }}</p>
        </div>
      </div>
    </div>

    <!-- Menu Sections -->
    <div class="px-4 py-4 space-y-4">
      <!-- 跨会话面试画像：反复暴露的薄弱点会在下一场面试被针对性追问 -->
      <div>
        <h3 class="mb-2 px-1 text-xs font-medium text-gray-500">
          {{ t('profile.weakness.title') }}
        </h3>
        <div class="rounded-xl bg-white p-4 shadow-sm">
          <p class="text-xs text-gray-400">{{ t('profile.weakness.subtitle') }}</p>

          <div v-if="loadingProfile" class="mt-3 space-y-2">
            <div class="h-4 w-2/3 animate-pulse rounded bg-gray-100" />
            <div class="h-4 w-1/2 animate-pulse rounded bg-gray-100" />
          </div>

          <template v-else-if="profile && profile.reportCount > 0">
            <div class="mt-3 flex items-center gap-4">
              <div>
                <p class="text-lg font-bold text-gray-800">{{ profile.reportCount }}</p>
                <p class="text-[11px] text-gray-400">{{ t('profile.weakness.reportCount') }}</p>
              </div>
              <div>
                <p class="text-lg font-bold text-gray-800">
                  {{ profile.avgScore ?? '-' }}
                </p>
                <p class="text-[11px] text-gray-400">{{ t('profile.weakness.avgScore') }}</p>
              </div>
              <div>
                <p class="text-lg font-bold text-gray-800">{{ profile.weaknessCount }}</p>
                <p class="text-[11px] text-gray-400">{{ t('profile.weakness.weakCount') }}</p>
              </div>
            </div>

            <ul v-if="profile.weaknesses.length" class="mt-3 space-y-2">
              <li
                v-for="item in profile.weaknesses"
                :key="item.category + item.topic"
                class="rounded-lg border border-gray-100 bg-gray-50/60 px-3 py-2"
              >
                <div class="flex items-center justify-between gap-2">
                  <p class="truncate text-xs font-medium text-gray-700">{{ item.topic }}</p>
                  <span class="shrink-0 rounded bg-amber-50 px-1.5 py-0.5 text-[10px] text-amber-700">
                    {{ item.categoryLabel }} ·
                    {{ t('profile.weakness.hitTimes', { count: item.hitCount }) }}
                  </span>
                </div>
                <p class="mt-0.5 text-[11px] text-gray-400">
                  {{ t('profile.weakness.lastScore') }} {{ item.latestScore }}
                </p>
              </li>
            </ul>
          </template>

          <p v-else class="mt-3 text-xs text-gray-400">
            {{ t('profile.weakness.noData') }}
          </p>
        </div>
      </div>

      <div v-for="section in menuSections" :key="section.title">
        <h3 class="mb-2 px-1 text-xs font-medium text-gray-500">{{ section.title }}</h3>
        <div class="overflow-hidden rounded-xl bg-white shadow-sm">
          <button
            v-for="(item, idx) in section.items"
            :key="item.path"
            @click="navigate(item.path)"
            class="flex w-full items-center gap-3 px-4 py-3.5 text-left transition active:bg-gray-50"
            :class="{ 'border-b border-gray-100': idx < section.items.length - 1 }"
          >
            <span class="text-xl">{{ item.icon }}</span>
            <div class="flex-1 min-w-0">
              <p class="text-sm font-medium text-gray-800">{{ item.label }}</p>
              <p class="text-xs text-gray-400 truncate">{{ item.desc }}</p>
            </div>
            <span class="text-gray-300">›</span>
          </button>
        </div>
      </div>

      <!-- Share App -->
      <div>
        <h3 class="mb-2 px-1 text-xs font-medium text-gray-500">{{ t('profile.about.title') }}</h3>
        <div class="overflow-hidden rounded-xl bg-white shadow-sm">
          <button
            @click="handleShare"
            class="flex w-full items-center gap-3 px-4 py-3.5 text-left transition active:bg-gray-50"
          >
            <span class="text-xl">📤</span>
            <div class="flex-1">
              <p class="text-sm font-medium text-gray-800">{{ t('profile.about.share') }}</p>
              <p class="text-xs text-gray-400">{{ t('profile.about.shareDesc') }}</p>
            </div>
            <span class="text-gray-300">›</span>
          </button>
        </div>
      </div>

      <!-- Version Info -->
      <div class="pt-2 text-center">
        <p class="text-xs text-gray-400">AI 面试官 v1.0.0</p>
        <p class="mt-1 text-xs text-gray-300">{{ t('profile.versionDesc') }}</p>
      </div>
    </div>
  </div>
</template>
