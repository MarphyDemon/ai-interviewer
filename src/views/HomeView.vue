<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useUserStore } from '@/stores/user'
import { getHomepageAvatars, setPreferredAvatar, type HomepageAvatarItem } from '@/api/avatar'
import OnboardingGuide from '@/components/common/OnboardingGuide.vue'

const { t } = useI18n()
const router = useRouter()
const userStore = useUserStore()

const avatars = ref<HomepageAvatarItem[]>([])
const loadingAvatars = ref(true)
const showOnboarding = ref(false)

onMounted(async () => {
  if (userStore.isLoggedIn) {
    try {
      avatars.value = await getHomepageAvatars()
    } catch {
      // 忽略加载失败
    } finally {
      loadingAvatars.value = false
    }
    const completed = localStorage.getItem('onboarding_completed')
    if (!completed) showOnboarding.value = true
  } else {
    loadingAvatars.value = false
  }
})

async function selectAvatar(avatar: HomepageAvatarItem) {
  try {
    await setPreferredAvatar(avatar.id)
    if (userStore.user) {
      userStore.user.preferredAvatarConfigId = avatar.id
    }
    // 更新本地状态
    avatars.value.forEach(a => { a.isSelected = (a.id === avatar.id) })
  } catch (e: any) {
    alert(e.message)
  }
}

function displayName(a: HomepageAvatarItem): string {
  return a.isDefault ? t('home.defaultAvatarName') : a.name
}

function isSelected(a: HomepageAvatarItem): boolean {
  return a.isSelected
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
          <button class="btn-primary w-full sm:w-auto min-h-[48px]" @click="go('/setup')">
            <svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M5 3l14 9-14 9V3z" />
            </svg>
            {{ t('home.ctaInterview') }}
          </button>
          <button class="btn-ghost w-full sm:w-auto min-h-[48px]" @click="go('/chat')">
            <svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M8 10h.01M12 10h.01M16 10h.01M21 12a8 8 0 01-8 8H7l-4 3v-6a8 8 0 018-11h2a8 8 0 018 6z" />
            </svg>
            {{ t('home.ctaChat') }}
          </button>
        </div>
      </div>
    </section>

    <!-- 数字人形象选择（登录用户可见） -->
    <section v-if="userStore.isLoggedIn" class="mx-auto max-w-5xl px-4 pb-16">
      <div class="mb-6 text-center">
        <h2 class="text-2xl font-bold text-gray-900 md:text-3xl">{{ t('home.avatarSectionTitle') }}</h2>
        <p class="mt-2 text-gray-500">{{ t('home.avatarSectionSubtitle') }}</p>
      </div>

      <div v-if="loadingAvatars" class="text-center text-gray-400">{{ t('common.loading') }}</div>
      <div v-else class="flex flex-wrap justify-center gap-4 md:gap-6">
        <button
          v-for="a in avatars"
          :key="a.id ?? 'default'"
          class="card group flex w-24 md:w-28 flex-col items-center gap-1.5 !p-2.5 md:!p-3 transition hover:-translate-y-1 hover:shadow-glow"
          :class="{ 'ring-2 ring-primary-400': isSelected(a) }"
          @click="selectAvatar(a)"
        >
          <div class="aspect-[9/16] w-full overflow-hidden rounded-xl border border-gray-200 bg-gray-50">
            <img
              :src="a.avatarImage"
              :alt="a.name"
              class="h-full w-full object-cover transition group-hover:scale-105"
              @error="($event) => { ($event.target as HTMLImageElement).style.display = 'none' }"
            />
          </div>
          <div class="avatar-name-wrapper w-full px-0.5 text-center">
            <span class="text-xs md:text-sm font-medium text-gray-700 leading-tight break-words">{{ displayName(a) }}</span>
          </div>
          <span v-if="isSelected(a)" class="text-xs text-primary-600">{{ t('home.avatarCurrent') }}</span>
          <span v-else class="text-xs text-gray-400">{{ t('home.avatarSelect') }}</span>
        </button>
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

    <!-- Footer -->
    <footer class="border-t border-primary-100/60 bg-white/50 backdrop-blur">
      <div class="mx-auto max-w-5xl px-4 py-8 text-center text-sm text-gray-400">
        {{ t('nav.brand') }} · {{ new Date().getFullYear() }}
      </div>
    </footer>

    <!-- 新手引导 -->
    <OnboardingGuide :show="showOnboarding" @finish="showOnboarding = false" />
  </div>
</template>
