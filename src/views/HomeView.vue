<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useUserStore } from '@/stores/user'
import { getAvatarList, setPreferredAvatar, type AvatarItem } from '@/api/avatar'

const { t } = useI18n()
const router = useRouter()
const userStore = useUserStore()

const avatars = ref<AvatarItem[]>([])

onMounted(async () => {
  if (userStore.isLoggedIn) {
    try {
      avatars.value = await getAvatarList()
    } catch {
      // 忽略加载失败
    }
  }
})

async function selectAvatar(id: number) {
  try {
    await setPreferredAvatar(id)
    if (userStore.user) {
      userStore.user.preferredAvatarId = id
    }
  } catch (e: any) {
    alert(e.message)
  }
}

const features = [
  { icon: 'interview', titleKey: 'home.feature1Title', descKey: 'home.feature1Desc' },
  { icon: 'chat', titleKey: 'home.feature2Title', descKey: 'home.feature2Desc' },
  { icon: 'knowledge', titleKey: 'home.feature3Title', descKey: 'home.feature3Desc' },
  { icon: 'report', titleKey: 'home.feature4Title', descKey: 'home.feature4Desc' },
] as const

function go(path: string) {
  router.push(path)
}
</script>

<template>
  <div>
    <!-- Hero -->
    <section class="relative overflow-hidden">
      <!-- 背景装饰 -->
      <div class="pointer-events-none absolute inset-0 -z-10">
        <div class="absolute -left-20 top-10 h-72 w-72 rounded-full bg-primary-300/30 blur-3xl animate-blob"></div>
        <div class="absolute right-0 top-40 h-80 w-80 rounded-full bg-accent-300/30 blur-3xl animate-blob [animation-delay:3s]"></div>
        <div class="absolute bottom-0 left-1/3 h-64 w-64 rounded-full bg-primary-200/40 blur-3xl animate-blob [animation-delay:6s]"></div>
      </div>

      <div class="mx-auto max-w-5xl px-4 py-20 text-center md:py-28">
        <span class="inline-flex items-center gap-2 rounded-full border border-primary-200 bg-white/70 px-4 py-1.5 text-sm font-medium text-primary-700 backdrop-blur animate-fade-up">
          <span class="h-2 w-2 rounded-full bg-gradient-brand"></span>
          {{ t('home.heroBadge') }}
        </span>

        <h1 class="mt-6 text-4xl font-extrabold leading-tight tracking-tight text-gray-900 animate-fade-up md:text-6xl [animation-delay:0.05s]">
          {{ t('home.heroTitle') }}
        </h1>

        <p class="mx-auto mt-6 max-w-2xl text-base leading-relaxed text-gray-600 animate-fade-up md:text-lg [animation-delay:0.1s]">
          {{ t('home.heroSubtitle') }}
        </p>

        <div class="mt-10 flex flex-col items-center justify-center gap-3 animate-fade-up sm:flex-row [animation-delay:0.15s]">
          <button class="btn-primary w-full sm:w-auto" @click="go('/setup')">
            <svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M5 3l14 9-14 9V3z" />
            </svg>
            {{ t('home.ctaInterview') }}
          </button>
          <button class="btn-ghost w-full sm:w-auto" @click="go('/chat')">
            <svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M8 10h.01M12 10h.01M16 10h.01M21 12a8 8 0 01-8 8H7l-4 3v-6a8 8 0 018-11h2a8 8 0 018 6z" />
            </svg>
            {{ t('home.ctaChat') }}
          </button>
        </div>

        <!-- 数字人预览卡 -->
        <div class="mx-auto mt-16 max-w-md animate-fade-up [animation-delay:0.2s]">
          <div class="card flex items-center gap-4 !p-5">
            <span class="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-gradient-brand text-white shadow-glow">
              <svg viewBox="0 0 24 24" class="h-7 w-7" fill="none" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M15 10l5 5-5 5M12 8v8M8 10l-5 5 5 5" />
              </svg>
            </span>
            <div class="text-left">
              <p class="font-semibold text-gray-800">{{ t('nav.brand') }}</p>
              <p class="text-sm text-gray-500">{{ t('home.heroBadge') }}</p>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Features -->
    <section class="mx-auto max-w-5xl px-4 pb-24">
      <div class="mb-10 text-center">
        <h2 class="text-2xl font-bold text-gray-900 md:text-3xl">{{ t('home.featuresTitle') }}</h2>
        <p class="mt-3 text-gray-500">{{ t('home.featuresSubtitle') }}</p>
      </div>

      <div class="grid gap-5 sm:grid-cols-2">
        <div
          v-for="(f, i) in features"
          :key="f.icon"
          class="card group transition hover:-translate-y-1 hover:shadow-glow animate-fade-up"
          :style="{ animationDelay: `${0.1 * i}s` }"
        >
          <span class="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-primary-50 text-primary-600 transition group-hover:bg-gradient-brand group-hover:text-white">
            <svg v-if="f.icon === 'interview'" viewBox="0 0 24 24" class="h-6 w-6" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M5 3l14 9-14 9V3z" /></svg>
            <svg v-else-if="f.icon === 'chat'" viewBox="0 0 24 24" class="h-6 w-6" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M8 10h.01M12 10h.01M16 10h.01M21 12a8 8 0 01-8 8H7l-4 3v-6a8 8 0 018-11h2a8 8 0 018 6z" /></svg>
            <svg v-else-if="f.icon === 'knowledge'" viewBox="0 0 24 24" class="h-6 w-6" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 6.25c-1.66-1.32-4.27-2.04-6.5-2.25C4.02 3.88 3 4.95 3 6.5v11c0 1.55 1.02 2.62 2.5 2.45 2.23-.21 4.84-.93 6.5-2.25 1.66 1.32 4.27 2.04 6.5 2.25 1.48.17 2.5-.9 2.5-2.45v-11c0-1.55-1.02-2.62-2.5-2.45-2.23.21-4.84.93-6.5 2.25zM12 6.25v13" /></svg>
            <svg v-else viewBox="0 0 24 24" class="h-6 w-6" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
          </span>
          <h3 class="text-lg font-semibold text-gray-800">{{ t(f.titleKey) }}</h3>
          <p class="mt-2 text-sm leading-relaxed text-gray-500">{{ t(f.descKey) }}</p>
        </div>
      </div>
    </section>

    <!-- 形象选择（仅登录用户可见） -->
    <section v-if="userStore.isLoggedIn && avatars.length" class="mx-auto max-w-5xl px-4 pb-24">
      <div class="mb-6 text-center">
        <h2 class="text-2xl font-bold text-gray-900">选择你的面试官形象</h2>
        <p class="mt-2 text-gray-500">从下方挑选一个数字人形象，将用于陪练与面试</p>
      </div>
      <div class="flex flex-wrap justify-center gap-4">
        <button
          v-for="a in avatars"
          :key="a.id"
          class="card flex w-40 flex-col items-center gap-3 !p-5 transition hover:-translate-y-1 hover:shadow-glow"
          :class="{ 'ring-2 ring-primary-400': userStore.user?.preferredAvatarId === a.id }"
          @click="selectAvatar(a.id)"
        >
          <span class="text-5xl">{{ a.extra?.emoji || '🙂' }}</span>
          <span class="text-sm font-medium text-gray-700">{{ a.name }}</span>
          <span v-if="userStore.user?.preferredAvatarId === a.id" class="text-xs text-primary-600">已选择</span>
        </button>
      </div>
    </section>

    <!-- Footer -->
    <footer class="border-t border-primary-100/60 bg-white/50 backdrop-blur">
      <div class="mx-auto max-w-5xl px-4 py-8 text-center text-sm text-gray-400">
        {{ t('nav.brand') }} · {{ new Date().getFullYear() }}
      </div>
    </footer>
  </div>
</template>
