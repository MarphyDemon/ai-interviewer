<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import * as orgApi from '@/api/org'
import type { CandidateRow, InviteRow, OrgInfo } from '@/api/org'
import { useJdStore } from '@/stores/jd'

/**
 * 企业控制台：面向 HR 的候选人初筛视图。
 *
 * 与个人练习的分工：
 * - 个人侧看「我自己练得怎么样」（历史 / 画像 / 实测指标）
 * - 企业侧看「这个岗位的候选人横向对比」（邀请 + 排名 + 报告）
 */

const { t } = useI18n()
const router = useRouter()
const jdStore = useJdStore()

const loading = ref(true)
const errorMsg = ref('')
const org = ref<OrgInfo | null>(null)
const invites = ref<InviteRow[]>([])
const candidates = ref<CandidateRow[]>([])
const filterInviteId = ref<number | null>(null)

const showCreate = ref(false)
const creating = ref(false)
const form = ref({
  position: '后端',
  jdId: null as number | null,
  difficulty: 'mid',
  duration: 30,
  style: 'friendly',
  note: '',
  expiresInDays: 30,
})
const lastCreatedLink = ref('')

const POSITIONS = ['前端', '后端', '算法', '产品', '测试']
const DIFFICULTIES = ['junior', 'mid', 'senior'] as const
const STYLES = ['friendly', 'strict', 'pressure'] as const
const DURATIONS = [15, 30, 45, 60]

const scoredCandidates = computed(() => candidates.value.filter((c) => c.totalScore !== null))
const avgOfAll = computed(() => {
  const list = scoredCandidates.value.map((c) => c.totalScore as number)
  if (!list.length) return null
  return Math.round((list.reduce((a, b) => a + b, 0) / list.length) * 10) / 10
})

function inviteLink(token: string) {
  return `${window.location.origin}/invite/${token}`
}

function fmtDate(iso: string | null) {
  if (!iso) return '—'
  return iso.replace('T', ' ').slice(0, 16)
}

async function load() {
  loading.value = true
  errorMsg.value = ''
  try {
    const [o, inv] = await Promise.all([orgApi.getMyOrg(), orgApi.listInvites()])
    org.value = o
    invites.value = inv
    await loadCandidates()
  } catch (e: any) {
    errorMsg.value = `${t('org.loadFailed')}${e?.message ?? e}`
  } finally {
    loading.value = false
  }
}

async function loadCandidates() {
  candidates.value = await orgApi.listCandidates(
    filterInviteId.value ? { inviteId: filterInviteId.value } : {},
  )
}

async function onCreate() {
  creating.value = true
  errorMsg.value = ''
  try {
    const res = await orgApi.createInvite({
      position: form.value.position,
      jdId: form.value.jdId,
      difficulty: form.value.difficulty,
      duration: form.value.duration,
      style: form.value.style,
      note: form.value.note,
      expiresInDays: form.value.expiresInDays,
    })
    lastCreatedLink.value = inviteLink(res.token)
    showCreate.value = false
    await load()
  } catch (e: any) {
    errorMsg.value = e?.message ?? String(e)
  } finally {
    creating.value = false
  }
}

async function onRevoke(invite: InviteRow) {
  if (!window.confirm(t('org.revokeConfirm', { position: invite.position }))) return
  try {
    await orgApi.revokeInvite(invite.id)
    await load()
  } catch (e: any) {
    errorMsg.value = e?.message ?? String(e)
  }
}

async function copyLink(token: string) {
  try {
    await navigator.clipboard.writeText(inviteLink(token))
    errorMsg.value = ''
    copiedToken.value = token
    setTimeout(() => {
      if (copiedToken.value === token) copiedToken.value = ''
    }, 2000)
  } catch {
    errorMsg.value = t('org.copyFailed')
  }
}

const copiedToken = ref('')

onMounted(async () => {
  await load()
  try {
    await jdStore.fetchJds()
  } catch {
    // JD 列表属增强项，失败不阻塞
  }
})
</script>

<template>
  <div class="mx-auto max-w-5xl px-4 py-6">
    <div class="mb-4 flex flex-wrap items-center justify-between gap-3">
      <div>
        <h1 class="text-lg font-bold text-gray-900">{{ t('org.title') }}</h1>
        <p class="mt-0.5 text-xs text-gray-500">
          {{ org ? `${org.name} · ${t('org.role.' + org.role)}` : t('org.subtitle') }}
        </p>
      </div>
      <div class="flex items-center gap-2">
        <button
          class="rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 transition hover:bg-gray-50"
          @click="load"
        >
          {{ t('org.refresh') }}
        </button>
        <button
          v-if="org?.canManage"
          class="rounded-lg bg-gradient-brand px-3 py-1.5 text-xs font-semibold text-white shadow-soft transition hover:opacity-90"
          @click="showCreate = !showCreate"
        >
          {{ t('org.createInvite') }}
        </button>
      </div>
    </div>

    <p v-if="errorMsg" class="mb-3 rounded-lg bg-red-50 px-3 py-2 text-xs text-red-600">
      {{ errorMsg }}
    </p>

    <div v-if="loading" class="space-y-3">
      <div class="h-20 animate-pulse rounded-xl bg-gray-100" />
      <div class="h-40 animate-pulse rounded-xl bg-gray-100" />
    </div>

    <template v-else>
      <!-- 概览 -->
      <div class="grid grid-cols-2 gap-3 md:grid-cols-4">
        <div class="rounded-xl border border-gray-200 bg-white p-3">
          <p class="text-xs font-semibold text-gray-500">{{ t('org.inviteCount') }}</p>
          <p class="mt-1 text-xl font-bold text-gray-900">{{ org?.inviteCount ?? 0 }}</p>
        </div>
        <div class="rounded-xl border border-gray-200 bg-white p-3">
          <p class="text-xs font-semibold text-gray-500">{{ t('org.candidateCount') }}</p>
          <p class="mt-1 text-xl font-bold text-gray-900">{{ org?.candidateCount ?? 0 }}</p>
        </div>
        <div class="rounded-xl border border-gray-200 bg-white p-3">
          <p class="text-xs font-semibold text-gray-500">{{ t('org.scoredCount') }}</p>
          <p class="mt-1 text-xl font-bold text-gray-900">{{ scoredCandidates.length }}</p>
        </div>
        <div class="rounded-xl border border-gray-200 bg-white p-3">
          <p class="text-xs font-semibold text-gray-500">{{ t('org.avgScore') }}</p>
          <p class="mt-1 text-xl font-bold text-gray-900">{{ avgOfAll ?? '—' }}</p>
        </div>
      </div>

      <!-- 新建邀请 -->
      <div v-if="showCreate" class="mt-4 rounded-xl border border-gray-200 bg-white p-4">
        <h2 class="mb-3 text-sm font-semibold text-gray-800">{{ t('org.createInvite') }}</h2>
        <div class="grid gap-3 md:grid-cols-2">
          <label class="block">
            <span class="text-xs font-medium text-gray-700">{{ t('setup.position') }}</span>
            <select
              v-model="form.position"
              class="mt-1 w-full rounded-lg border border-gray-200 px-3 py-2 text-sm"
            >
              <option v-for="p in POSITIONS" :key="p" :value="p">{{ t('positions.' + p) }}</option>
            </select>
          </label>
          <label class="block">
            <span class="text-xs font-medium text-gray-700">{{ t('org.jdOptional') }}</span>
            <select
              v-model="form.jdId"
              class="mt-1 w-full rounded-lg border border-gray-200 px-3 py-2 text-sm"
            >
              <option :value="null">{{ t('org.noJd') }}</option>
              <option v-for="jd in jdStore.jds" :key="jd.id" :value="jd.id">{{ jd.title }}</option>
            </select>
          </label>
          <label class="block">
            <span class="text-xs font-medium text-gray-700">{{ t('setup.difficulty') }}</span>
            <select
              v-model="form.difficulty"
              class="mt-1 w-full rounded-lg border border-gray-200 px-3 py-2 text-sm"
            >
              <option v-for="d in DIFFICULTIES" :key="d" :value="d">{{ t('difficulty.' + d) }}</option>
            </select>
          </label>
          <label class="block">
            <span class="text-xs font-medium text-gray-700">{{ t('setup.duration') }}</span>
            <select
              v-model.number="form.duration"
              class="mt-1 w-full rounded-lg border border-gray-200 px-3 py-2 text-sm"
            >
              <option v-for="d in DURATIONS" :key="d" :value="d">{{ d }}</option>
            </select>
          </label>
          <label class="block">
            <span class="text-xs font-medium text-gray-700">{{ t('setup.interviewerStyle') }}</span>
            <select
              v-model="form.style"
              class="mt-1 w-full rounded-lg border border-gray-200 px-3 py-2 text-sm"
            >
              <option v-for="s in STYLES" :key="s" :value="s">{{ t('styles.' + s) }}</option>
            </select>
          </label>
          <label class="block">
            <span class="text-xs font-medium text-gray-700">{{ t('org.expiresInDays') }}</span>
            <input
              v-model.number="form.expiresInDays"
              type="number"
              min="1"
              max="365"
              class="mt-1 w-full rounded-lg border border-gray-200 px-3 py-2 text-sm"
            />
          </label>
          <label class="block md:col-span-2">
            <span class="text-xs font-medium text-gray-700">{{ t('org.note') }}</span>
            <input
              v-model="form.note"
              type="text"
              maxlength="120"
              :placeholder="t('org.notePlaceholder')"
              class="mt-1 w-full rounded-lg border border-gray-200 px-3 py-2 text-sm"
            />
          </label>
        </div>
        <button
          class="mt-3 rounded-lg bg-gradient-brand px-4 py-2 text-xs font-semibold text-white shadow-soft transition hover:opacity-90 disabled:opacity-50"
          :disabled="creating"
          @click="onCreate"
        >
          {{ creating ? t('org.creating') : t('org.createInvite') }}
        </button>
      </div>

      <!-- 刚生成的链接 -->
      <div
        v-if="lastCreatedLink"
        class="mt-4 rounded-xl border border-green-200 bg-green-50 px-3 py-3 text-xs text-green-800"
      >
        <p class="font-semibold">{{ t('org.createdHint') }}</p>
        <p class="mt-1 break-all font-mono">{{ lastCreatedLink }}</p>
      </div>

      <!-- 邀请列表 -->
      <div class="mt-6">
        <h2 class="mb-2 text-sm font-semibold text-gray-800">{{ t('org.invites') }}</h2>
        <p
          v-if="!invites.length"
          class="rounded-xl border border-dashed border-gray-200 px-3 py-8 text-center text-xs text-gray-400"
        >
          {{ t('org.noInvites') }}
        </p>
        <div v-else class="overflow-hidden rounded-xl border border-gray-200 bg-white">
          <table class="w-full text-left text-xs">
            <thead class="bg-gray-50 text-gray-500">
              <tr>
                <th class="px-3 py-2 font-medium">{{ t('setup.position') }}</th>
                <th class="px-3 py-2 font-medium">{{ t('setup.difficulty') }}</th>
                <th class="px-3 py-2 font-medium">{{ t('org.candidates') }}</th>
                <th class="px-3 py-2 font-medium">{{ t('org.avgScore') }}</th>
                <th class="px-3 py-2 font-medium">{{ t('org.status') }}</th>
                <th class="px-3 py-2 font-medium">{{ t('org.actions') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="inv in invites" :key="inv.id" class="border-t border-gray-100">
                <td class="px-3 py-2">
                  <span class="font-medium text-gray-900">{{ inv.position }}</span>
                  <span v-if="inv.note" class="ml-1 text-gray-400">{{ inv.note }}</span>
                </td>
                <td class="px-3 py-2 text-gray-600">{{ t('difficulty.' + inv.difficulty) }}</td>
                <td class="px-3 py-2 text-gray-600">
                  {{ inv.candidateCount }}
                  <span class="text-gray-400">/ {{ inv.scoredCount }} {{ t('org.scored') }}</span>
                </td>
                <td class="px-3 py-2 text-gray-600">{{ inv.avgScore ?? '—' }}</td>
                <td class="px-3 py-2">
                  <span
                    class="rounded px-1.5 py-0.5 text-[11px]"
                    :class="inv.active ? 'bg-green-50 text-green-700' : 'bg-gray-100 text-gray-500'"
                  >
                    {{ inv.active ? t('org.active') : t('org.inactive') }}
                  </span>
                </td>
                <td class="px-3 py-2">
                  <div class="flex flex-wrap gap-2">
                    <button class="text-primary-600 hover:underline" @click="copyLink(inv.token)">
                      {{ copiedToken === inv.token ? t('org.copied') : t('org.copyLink') }}
                    </button>
                    <a
                      class="text-primary-600 hover:underline"
                      :href="inviteLink(inv.token)"
                      target="_blank"
                      rel="noopener"
                    >
                      {{ t('org.open') }}
                    </a>
                    <button
                      v-if="inv.active && org?.canManage"
                      class="text-red-600 hover:underline"
                      @click="onRevoke(inv)"
                    >
                      {{ t('org.revoke') }}
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- 候选人排名 -->
      <div class="mt-6">
        <div class="mb-2 flex flex-wrap items-center justify-between gap-2">
          <h2 class="text-sm font-semibold text-gray-800">{{ t('org.ranking') }}</h2>
          <select
            v-model="filterInviteId"
            class="rounded-lg border border-gray-200 bg-white px-2 py-1.5 text-xs text-gray-700"
            @change="loadCandidates"
          >
            <option :value="null">{{ t('org.allInvites') }}</option>
            <option v-for="inv in invites" :key="inv.id" :value="inv.id">
              {{ inv.position }} · {{ fmtDate(inv.createdAt) }}
            </option>
          </select>
        </div>

        <p
          v-if="!candidates.length"
          class="rounded-xl border border-dashed border-gray-200 px-3 py-8 text-center text-xs text-gray-400"
        >
          {{ t('org.noCandidates') }}
        </p>
        <div v-else class="overflow-hidden rounded-xl border border-gray-200 bg-white">
          <table class="w-full text-left text-xs">
            <thead class="bg-gray-50 text-gray-500">
              <tr>
                <th class="px-3 py-2 font-medium">#</th>
                <th class="px-3 py-2 font-medium">{{ t('org.candidateName') }}</th>
                <th class="px-3 py-2 font-medium">{{ t('setup.position') }}</th>
                <th class="px-3 py-2 font-medium">{{ t('org.score') }}</th>
                <th class="px-3 py-2 font-medium">{{ t('org.status') }}</th>
                <th class="px-3 py-2 font-medium">{{ t('org.startedAt') }}</th>
                <th class="px-3 py-2 font-medium">{{ t('org.actions') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, idx) in candidates" :key="row.candidateId" class="border-t border-gray-100">
                <td class="px-3 py-2 text-gray-400">{{ idx + 1 }}</td>
                <td class="px-3 py-2">
                  <span class="font-medium text-gray-900">{{ row.name }}</span>
                  <span v-if="row.email" class="ml-1 text-gray-400">{{ row.email }}</span>
                </td>
                <td class="px-3 py-2 text-gray-600">{{ row.position }}</td>
                <td class="px-3 py-2">
                  <span v-if="row.totalScore !== null" class="font-bold text-gray-900">
                    {{ row.totalScore }}
                  </span>
                  <span v-else class="text-gray-400">—</span>
                </td>
                <td class="px-3 py-2 text-gray-600">{{ row.status }}</td>
                <td class="px-3 py-2 text-gray-500">{{ fmtDate(row.startedAt) }}</td>
                <td class="px-3 py-2">
                  <button
                    v-if="row.interviewId && row.totalScore !== null"
                    class="text-primary-600 hover:underline"
                    @click="router.push(`/report/${row.interviewId}`)"
                  >
                    {{ t('org.viewReport') }}
                  </button>
                  <span v-else class="text-gray-300">{{ t('org.noReport') }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- 成员 -->
      <div v-if="org?.members?.length" class="mt-6">
        <h2 class="mb-2 text-sm font-semibold text-gray-800">{{ t('org.members') }}</h2>
        <div class="overflow-hidden rounded-xl border border-gray-200 bg-white">
          <table class="w-full text-left text-xs">
            <thead class="bg-gray-50 text-gray-500">
              <tr>
                <th class="px-3 py-2 font-medium">{{ t('org.memberName') }}</th>
                <th class="px-3 py-2 font-medium">{{ t('org.roleLabel') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="m in org.members" :key="m.userId" class="border-t border-gray-100">
                <td class="px-3 py-2 text-gray-900">{{ m.username }}</td>
                <td class="px-3 py-2 text-gray-600">{{ t('org.role.' + m.role) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>
