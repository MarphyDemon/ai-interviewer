<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import * as inviteApi from '@/api/invite'
import type { InviteInfo } from '@/api/invite'
import { useInterviewStore } from '@/stores/interview'
import { useUserStore } from '@/stores/user'

/**
 * 候选人入口页（公开路由 /invite/:token）。
 *
 * 候选人不需要注册：填姓名后后端会创建一个 role="candidate" 的无密码用户并直接签发 token，
 * 之后跳转到与个人练习完全相同的面试页。
 */

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const store = useInterviewStore()
const userStore = useUserStore()

const token = String(route.params.token || '')

const loading = ref(true)
const starting = ref(false)
const info = ref<InviteInfo | null>(null)
const notFound = ref(false)
const name = ref('')
const email = ref('')
const errorMsg = ref('')

onMounted(async () => {
  try {
    info.value = await inviteApi.getInvite(token)
  } catch {
    notFound.value = true
  } finally {
    loading.value = false
  }
})

async function start() {
  errorMsg.value = ''
  if (!name.value.trim()) {
    errorMsg.value = t('invite.nameRequired')
    return
  }

  // 同一浏览器里如果已经登录了别的账号（例如 HR 自己点开链接试跑），
  // 这里会覆盖登录态，先让用户确认，避免"莫名其妙被登出"。
  if (userStore.isLoggedIn && userStore.user?.role !== 'candidate') {
    if (!window.confirm(t('invite.switchAccountConfirm'))) return
  }

  starting.value = true
  try {
    const res = await inviteApi.startByInvite(token, {
      name: name.value.trim(),
      email: email.value.trim(),
    })
    userStore.setToken(res.token)
    store.startFromInvite(res)
    router.push('/interview')
  } catch (e: any) {
    errorMsg.value = e?.message ?? String(e)
  } finally {
    starting.value = false
  }
}
</script>

<template>
  <div class="mx-auto flex max-w-lg flex-col px-4 py-10">
    <div v-if="loading" class="space-y-3">
      <div class="h-8 w-2/3 animate-pulse rounded bg-gray-100" />
      <div class="h-32 animate-pulse rounded-xl bg-gray-100" />
    </div>

    <div
      v-else-if="notFound"
      class="rounded-xl border border-red-200 bg-red-50 px-4 py-6 text-center text-sm text-red-600"
    >
      {{ t('invite.invalid') }}
    </div>

    <template v-else-if="info">
      <h1 class="text-xl font-bold text-gray-900">{{ info.position }}</h1>
      <p class="mt-1 text-xs text-gray-500">
        {{ info.orgName }}<span v-if="info.jdTitle"> · {{ info.jdTitle }}</span>
      </p>

      <div
        v-if="!info.active"
        class="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs leading-relaxed text-amber-800"
      >
        {{ t('invite.inactive') }}
      </div>

      <dl class="mt-5 grid grid-cols-3 gap-3">
        <div class="rounded-xl border border-gray-200 bg-white p-3">
          <dt class="text-[11px] font-semibold text-gray-500">{{ t('setup.difficulty') }}</dt>
          <dd class="mt-0.5 text-sm font-bold text-gray-900">
            {{ t(`difficulty.${info.difficulty}`) }}
          </dd>
        </div>
        <div class="rounded-xl border border-gray-200 bg-white p-3">
          <dt class="text-[11px] font-semibold text-gray-500">{{ t('setup.duration') }}</dt>
          <dd class="mt-0.5 text-sm font-bold text-gray-900">{{ info.duration }} min</dd>
        </div>
        <div class="rounded-xl border border-gray-200 bg-white p-3">
          <dt class="text-[11px] font-semibold text-gray-500">{{ t('setup.interviewerStyle') }}</dt>
          <dd class="mt-0.5 text-sm font-bold text-gray-900">
            {{ t(`styles.${info.style}`) }}
          </dd>
        </div>
      </dl>

      <p v-if="info.note" class="mt-4 rounded-xl bg-gray-50 px-3 py-2 text-xs leading-relaxed text-gray-600">
        {{ info.note }}
      </p>

      <div class="mt-6 space-y-3">
        <label class="block">
          <span class="text-xs font-medium text-gray-700">{{ t('invite.name') }}</span>
          <input
            v-model="name"
            type="text"
            maxlength="32"
            :placeholder="t('invite.namePlaceholder')"
            class="mt-1 w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:border-primary-400 focus:outline-none"
            @keyup.enter="start"
          />
        </label>
        <label class="block">
          <span class="text-xs font-medium text-gray-700">{{ t('invite.email') }}</span>
          <input
            v-model="email"
            type="email"
            maxlength="64"
            :placeholder="t('invite.emailPlaceholder')"
            class="mt-1 w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:border-primary-400 focus:outline-none"
          />
        </label>
      </div>

      <p v-if="errorMsg" class="mt-3 rounded-lg bg-red-50 px-3 py-2 text-xs text-red-600">
        {{ errorMsg }}
      </p>

      <button
        class="mt-5 rounded-lg bg-gradient-brand px-4 py-2.5 text-sm font-semibold text-white shadow-soft transition hover:opacity-90 disabled:opacity-50"
        :disabled="starting || !info.active"
        @click="start"
      >
        {{ starting ? t('invite.starting') : t('invite.start') }}
      </button>

      <p class="mt-3 text-[11px] leading-relaxed text-gray-400">{{ t('invite.hint') }}</p>
    </template>
  </div>
</template>
