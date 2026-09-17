<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useUserStore } from '@/stores/user'
import * as settingsApi from '@/api/settings'
import * as adminApi from '@/api/admin'
import { setLanguage, getLanguage } from '@/i18n'
import { THEME_COLORS, applyThemeColor, getThemeColor, normalizeThemeColor } from '@/utils/theme'
import type { NotificationSettings, UserQuota } from '@/types'
import type { UserListItem } from '@/api/admin'

const { t } = useI18n()
const route = useRoute()
const userStore = useUserStore()

/** 由路由守卫重定向而来：该页面（企业控制台 / 实测指标）需要企业身份 */
const needEnterprise = ref(route.query.needEnterprise === '1')

const activeTab = ref<'personal' | 'platform'>('personal')
const isSaving = ref(false)

// Personal settings
const personal = ref<{
  preferredAvatarConfigId: number | null
  preferredPosition: string
  language: 'zh' | 'en'
  theme: string
  notificationSettings: NotificationSettings
  quota: UserQuota | null
}>({
  preferredAvatarConfigId: null,
  preferredPosition: '',
  language: getLanguage(),
  theme: getThemeColor(),
  notificationSettings: { collaboration: true, review: true, system: true },
  quota: null,
})

// Admin: users management
const users = ref<UserListItem[]>([])
const showPromoteModal = ref(false)
const promoteTarget = ref<UserListItem | null>(null)
const promoteRole = ref<'user' | 'admin'>('user')

// Admin: stats
const stats = ref<adminApi.PlatformStats | null>(null)

const isAdmin = computed(() => userStore.isAdmin)

const notifItems = computed<{ key: keyof NotificationSettings; label: string }[]>(() => [
  { key: 'collaboration', label: t('settings.notifCollaboration') },
  { key: 'review', label: t('settings.notifReview') },
  { key: 'system', label: t('settings.notifSystem') },
])

/** 岗位方向：存储值沿用中文（与历史数据一致），展示按当前语言翻译 */
const POSITION_LABEL_KEYS: Record<string, string> = {
  前端: 'settings.positions.frontend',
  后端: 'settings.positions.backend',
  算法: 'settings.positions.algorithm',
  产品: 'settings.positions.product',
  测试: 'settings.positions.testing',
  测试开发: 'settings.positions.testDev',
  运维: 'settings.positions.ops',
}

const positions = ['', '前端', '后端', '算法', '产品', '测试', '测试开发', '运维']

function positionLabel(value: string) {
  if (!value) return t('settings.notSet')
  const key = POSITION_LABEL_KEYS[value]
  return key ? t(key) : value
}

function planLabel(plan: string) {
  return t(`settings.plans.${plan}`)
}

/** 语言切换：立即生效（vue-i18n locale + localStorage）并随设置保存 */
function selectLanguage(code: 'zh' | 'en') {
  personal.value.language = code
  setLanguage(code)
}

/** 主题色切换：立即改写 <html data-theme>，全站主色随之变化 */
function selectThemeColor(id: string) {
  personal.value.theme = id
  applyThemeColor(id)
}

// 邀请码兑换
const inviteCodeInput = ref('')
const redeemLoading = ref(false)
const redeemMessage = ref('')
const redeemSuccess = ref(false)

// 管理员：邀请码管理
const inviteCodes = ref<adminApi.InviteCodeItem[]>([])
const newInvitePlan = ref('standard')
const newInviteMaxUses = ref(10)
const newInviteNote = ref('')

async function loadInviteCodes() {
  try {
    inviteCodes.value = await adminApi.getInviteCodes()
  } catch {}
}

async function handleCreateInviteCode() {
  try {
    const res = await adminApi.createInviteCode({
      plan: newInvitePlan.value,
      maxUses: newInviteMaxUses.value,
      note: newInviteNote.value || undefined,
    })
    alert(`邀请码生成成功: ${res.code}`)
    newInviteNote.value = ''
    await loadInviteCodes()
  } catch (e: any) {
    alert(e?.response?.data?.detail || '生成失败')
  }
}

async function handleRedeem() {
  const code = inviteCodeInput.value.trim().toUpperCase()
  if (!code) return
  redeemLoading.value = true
  redeemMessage.value = ''
  try {
    const res = await adminApi.redeemInviteCode(code)
    redeemSuccess.value = true
    redeemMessage.value = t('settings.redeemSuccess', { plan: planLabel(res.plan) })
    inviteCodeInput.value = ''
    // 兑换到企业版后即可访问企业侧页面
    if (res.plan === 'enterprise') needEnterprise.value = false
    await loadPersonal()
  } catch (e: any) {
    redeemSuccess.value = false
    redeemMessage.value = e?.message || t('settings.redeemFailed')
  } finally {
    redeemLoading.value = false
  }
}

async function loadPersonal() {
  try {
    const data = await settingsApi.getPersonalSettings()
    // 历史数据里的 light / dark 归一化为有效主题色 id，保证按钮选中态正确
    personal.value = { ...data, theme: normalizeThemeColor(data.theme) }
    // 服务端保存的偏好立即生效，保证换设备后语言/主题色一致
    if (data.language) setLanguage(data.language)
    applyThemeColor(data.theme)
  } catch (e) {
    console.error('加载设置失败', e)
  }
}

async function savePersonal() {
  isSaving.value = true
  try {
    await settingsApi.updatePersonalSettings({
      preferredAvatarConfigId: personal.value.preferredAvatarConfigId,
      preferredPosition: personal.value.preferredPosition,
      language: personal.value.language,
      theme: personal.value.theme,
      notificationSettings: personal.value.notificationSettings,
    })
    await userStore.fetchMe()
  } catch (e) {
    console.error('保存设置失败', e)
  } finally {
    isSaving.value = false
  }
}

async function loadUsers() {
  try {
    users.value = await adminApi.getUsers()
  } catch (e) {
    console.error('加载用户列表失败', e)
  }
}

async function loadStats() {
  try {
    stats.value = await adminApi.getPlatformStats()
  } catch (e) {
    console.error('加载统计失败', e)
  }
}

function openPromoteModal(user: UserListItem) {
  promoteTarget.value = user
  promoteRole.value = user.role
  showPromoteModal.value = true
}

async function confirmPromote() {
  if (!promoteTarget.value) return
  await adminApi.promoteUser(promoteTarget.value.id, promoteRole.value)
  showPromoteModal.value = false
  await loadUsers()
}

onMounted(async () => {
  await loadPersonal()
  if (isAdmin.value) {
    await Promise.all([loadUsers(), loadStats(), loadInviteCodes()])
  }
})
</script>

<template>
  <div class="max-w-4xl mx-auto p-4 md:p-6">
    <h1 class="text-2xl md:text-3xl font-bold text-gray-900 mb-6">{{ t('settings.title') }}</h1>

    <!-- 企业侧页面守卫提示 -->
    <div
      v-if="needEnterprise"
      class="mb-6 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-relaxed text-amber-800"
    >
      {{ t('settings.enterpriseOnlyHint') }}
    </div>

    <!-- Tab 切换 -->
    <div class="flex border-b border-gray-200 mb-6">
      <button
        @click="activeTab = 'personal'"
        :class="[
          'px-4 py-3 text-sm font-medium border-b-2 transition-colors',
          activeTab === 'personal'
            ? 'border-blue-600 text-blue-600'
            : 'border-transparent text-gray-500 hover:text-gray-700',
        ]"
      >
        {{ t('settings.personal') }}
      </button>
      <button
        v-if="isAdmin"
        @click="activeTab = 'platform'"
        :class="[
          'px-4 py-3 text-sm font-medium border-b-2 transition-colors',
          activeTab === 'platform'
            ? 'border-blue-600 text-blue-600'
            : 'border-transparent text-gray-500 hover:text-gray-700',
        ]"
      >
        {{ t('settings.platform') }}
      </button>
    </div>

    <!-- 个人设置 -->
    <div v-if="activeTab === 'personal'" class="space-y-6">
      <section class="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
        <h2 class="text-lg font-semibold text-gray-900 mb-4">{{ t('settings.preferences') }}</h2>
        <div class="space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('settings.defaultPosition') }}</label>
            <select
              v-model="personal.preferredPosition"
              class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option v-for="p in positions" :key="p" :value="p">
                {{ positionLabel(p) }}
              </option>
            </select>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('settings.language') }}</label>
            <div class="flex gap-2">
              <button
                v-for="lang in [{ code: 'zh', label: '中文' }, { code: 'en', label: 'English' }]"
                :key="lang.code"
                @click="selectLanguage(lang.code as 'zh' | 'en')"
                :class="[
                  'px-4 py-2 rounded-lg text-sm font-medium border transition-colors',
                  personal.language === lang.code
                    ? 'border-blue-600 bg-blue-50 text-blue-700'
                    : 'border-gray-300 text-gray-700 hover:bg-gray-50',
                ]"
              >
                {{ lang.label }}
              </button>
            </div>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">{{ t('settings.theme') }}</label>
            <div class="flex flex-wrap gap-2">
              <button
                v-for="color in THEME_COLORS"
                :key="color.id"
                @click="selectThemeColor(color.id)"
                :class="[
                  'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium border transition-colors',
                  personal.theme === color.id
                    ? 'border-blue-600 bg-blue-50 text-blue-700'
                    : 'border-gray-300 text-gray-700 hover:bg-gray-50',
                ]"
              >
                <span
                  class="h-4 w-4 rounded-full"
                  :style="{ background: `linear-gradient(135deg, ${color.primary} 0%, ${color.accent} 100%)` }"
                />
                {{ t(`settings.themes.${color.id}`) }}
              </button>
            </div>
          </div>
        </div>
      </section>

      <section class="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
        <h2 class="text-lg font-semibold text-gray-900 mb-4">{{ t('settings.notifications') }}</h2>
        <div class="space-y-3">
          <label
            v-for="item in notifItems"
            :key="item.key"
            class="flex items-center justify-between py-2"
          >
            <span class="text-sm text-gray-700">{{ item.label }}</span>
            <button
              @click="personal.notificationSettings[item.key] = !personal.notificationSettings[item.key]"
              :class="[
                'relative inline-flex h-6 w-11 items-center rounded-full transition-colors',
                personal.notificationSettings[item.key] ? 'bg-blue-600' : 'bg-gray-300',
              ]"
            >
              <span
                :class="[
                  'inline-block h-4 w-4 rounded-full bg-white shadow transition-transform',
                  personal.notificationSettings[item.key] ? 'translate-x-6' : 'translate-x-1',
                ]"
              />
            </button>
          </label>
        </div>
      </section>

      <section v-if="personal.quota" class="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
        <h2 class="text-lg font-semibold text-gray-900 mb-4">{{ t('settings.quota') }}</h2>
        <div class="grid grid-cols-3 gap-4">
          <div class="text-center p-3 bg-gray-50 rounded-lg">
            <div class="text-2xl font-bold text-gray-900">
              {{ personal.quota.interviewUsed }} / {{ personal.quota.interviewLimit }}
            </div>
            <div class="text-xs text-gray-500 mt-1">{{ t('settings.interviewCount') }}</div>
          </div>
          <div class="text-center p-3 bg-gray-50 rounded-lg">
            <div class="text-2xl font-bold text-gray-900">
              {{ personal.quota.knowledgeUsed }} / {{ personal.quota.knowledgeLimit }}
            </div>
            <div class="text-xs text-gray-500 mt-1">{{ t('settings.knowledgeDocs') }}</div>
          </div>
          <div class="text-center p-3 bg-gray-50 rounded-lg">
            <div class="text-2xl font-bold text-gray-900">
              {{ personal.quota.aiCallsUsed }} / {{ personal.quota.aiCallsLimit }}
            </div>
            <div class="text-xs text-gray-500 mt-1">{{ t('settings.aiCalls') }}</div>
          </div>
        </div>
        <div class="mt-3 text-center">
          <span class="inline-block px-3 py-1 rounded-full text-xs font-medium"
            :class="{
              'bg-green-100 text-green-700': personal.quota.plan === 'free',
              'bg-blue-100 text-blue-700': personal.quota.plan === 'standard',
              'bg-purple-100 text-purple-700': personal.quota.plan === 'enterprise',
            }">
            {{ planLabel(personal.quota.plan) }}
          </span>
        </div>
      </section>

      <div class="flex justify-end">
        <button
          @click="savePersonal"
          :disabled="isSaving"
          class="px-6 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
        >
          {{ isSaving ? t('settings.saving') : t('settings.saveProfile') }}
        </button>
      </div>

      <!-- 邀请码兑换 -->
      <section class="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
        <h2 class="text-lg font-semibold text-gray-900 mb-4">{{ t('settings.redeemTitle') }}</h2>
        <div class="flex gap-2">
          <input v-model="inviteCodeInput" :placeholder="t('settings.redeemPlaceholder')"
            class="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 uppercase" />
          <button @click="handleRedeem" :disabled="!inviteCodeInput.trim() || redeemLoading"
            class="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-50">
            {{ redeemLoading ? t('settings.redeeming') : t('settings.redeem') }}
          </button>
        </div>
        <p v-if="redeemMessage" :class="['mt-2 text-sm', redeemSuccess ? 'text-green-600' : 'text-red-600']">
          {{ redeemMessage }}
        </p>
        <p class="text-xs text-gray-400 mt-2">{{ t('settings.redeemHint') }}</p>
      </section>
    </div>

    <!-- 平台管理 -->
    <div v-if="activeTab === 'platform' && isAdmin" class="space-y-6">
      <!-- 统计看板 -->
      <section v-if="stats" class="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
        <h2 class="text-lg font-semibold text-gray-900 mb-4">平台概览</h2>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div class="p-3 bg-blue-50 rounded-lg">
            <div class="text-xl font-bold text-blue-900">{{ stats.totalUsers }}</div>
            <div class="text-xs text-blue-600">总用户数</div>
          </div>
          <div class="p-3 bg-green-50 rounded-lg">
            <div class="text-xl font-bold text-green-900">{{ stats.totalInterviews }}</div>
            <div class="text-xs text-green-600">总面试数</div>
          </div>
          <div class="p-3 bg-purple-50 rounded-lg">
            <div class="text-xl font-bold text-purple-900">{{ stats.totalKnowledgeDocs }}</div>
            <div class="text-xs text-purple-600">知识文档</div>
          </div>
          <div class="p-3 bg-orange-50 rounded-lg">
            <div class="text-xl font-bold text-orange-900">{{ stats.totalReports }}</div>
            <div class="text-xs text-orange-600">面试报告</div>
          </div>
        </div>
        <div class="mt-4 flex gap-4 text-sm">
          <span class="text-gray-600">免费版: {{ stats.freePlanUsers }}</span>
          <span class="text-gray-600">标准版: {{ stats.standardPlanUsers }}</span>
          <span class="text-gray-600">企业版: {{ stats.enterprisePlanUsers }}</span>
        </div>
      </section>

      <!-- 用户管理 -->
      <section class="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
        <h2 class="text-lg font-semibold text-gray-900 mb-4">用户管理</h2>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-gray-200 text-left text-xs font-medium text-gray-500 uppercase">
                <th class="pb-2">用户名</th>
                <th class="pb-2">角色</th>
                <th class="pb-2">套餐</th>
                <th class="pb-2">注册时间</th>
                <th class="pb-2">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="u in users" :key="u.id" class="border-b border-gray-100">
                <td class="py-3 font-medium text-gray-900">{{ u.username }}</td>
                <td class="py-3">
                  <span class="px-2 py-0.5 rounded-full text-xs font-medium"
                    :class="u.role === 'admin' ? 'bg-purple-100 text-purple-700' : 'bg-gray-100 text-gray-600'">
                    {{ u.role === 'admin' ? '管理员' : '普通用户' }}
                  </span>
                </td>
                <td class="py-3 text-gray-600">{{ u.plan }}</td>
                <td class="py-3 text-gray-500">{{ new Date(u.createdAt).toLocaleDateString('zh-CN') }}</td>
                <td class="py-3">
                  <button
                    @click="openPromoteModal(u)"
                    class="text-blue-600 hover:text-blue-800 text-sm font-medium"
                  >
                    {{ u.role === 'admin' ? '降级' : '提升' }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- 邀请码管理 -->
      <section class="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-lg font-semibold text-gray-900">邀请码管理</h2>
          <button @click="loadInviteCodes" class="text-sm text-blue-600 hover:text-blue-800">刷新</button>
        </div>
        <div class="flex gap-2 mb-4">
          <select v-model="newInvitePlan" class="border border-gray-300 rounded-lg px-3 py-2 text-sm">
            <option value="standard">标准版</option>
            <option value="enterprise">企业版</option>
          </select>
          <input v-model.number="newInviteMaxUses" type="number" min="1" max="1000" placeholder="最大使用次数"
            class="w-32 border border-gray-300 rounded-lg px-3 py-2 text-sm" />
          <input v-model="newInviteNote" placeholder="备注（可选）"
            class="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm" />
          <button @click="handleCreateInviteCode"
            class="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700">
            生成
          </button>
        </div>
        <div v-if="inviteCodes.length > 0" class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-gray-200 text-left text-xs font-medium text-gray-500 uppercase">
                <th class="pb-2">邀请码</th>
                <th class="pb-2">套餐</th>
                <th class="pb-2">使用次数</th>
                <th class="pb-2">状态</th>
                <th class="pb-2">过期时间</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="c in inviteCodes" :key="c.id" class="border-b border-gray-100">
                <td class="py-3 font-mono text-gray-900">{{ c.code }}</td>
                <td class="py-3">
                  <span class="px-2 py-0.5 rounded-full text-xs"
                    :class="c.plan === 'enterprise' ? 'bg-purple-100 text-purple-700' : 'bg-blue-100 text-blue-700'">
                    {{ c.plan === 'standard' ? '标准版' : '企业版' }}
                  </span>
                </td>
                <td class="py-3 text-gray-600">{{ c.usedCount }} / {{ c.maxUses }}</td>
                <td class="py-3">
                  <span :class="c.isActive ? 'text-green-600' : 'text-gray-400'">
                    {{ c.isActive ? '活跃' : '已失效' }}
                  </span>
                </td>
                <td class="py-3 text-gray-500">{{ c.expiresAt ? new Date(c.expiresAt).toLocaleDateString('zh-CN') : '永不过期' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else class="text-center py-4 text-gray-500 text-sm">暂无邀请码</div>
      </section>
    </div>

    <!-- 提升角色弹窗 -->
    <div v-if="showPromoteModal" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
      @click.self="showPromoteModal = false">
      <div class="bg-white rounded-xl p-6 w-full max-w-sm mx-4">
        <h3 class="text-lg font-semibold text-gray-900 mb-4">修改用户角色</h3>
        <p class="text-sm text-gray-600 mb-4">
          用户 <strong>{{ promoteTarget?.username }}</strong> 当前角色: {{ promoteTarget?.role === 'admin' ? '管理员' : '普通用户' }}
        </p>
        <div class="space-y-2 mb-6">
          <label
            v-for="r in [{ v: 'user', label: '普通用户' }, { v: 'admin', label: '管理员' }]"
            :key="r.v"
            class="flex items-center gap-2 p-3 border rounded-lg cursor-pointer transition-colors"
            :class="promoteRole === r.v ? 'border-blue-600 bg-blue-50' : 'border-gray-200 hover:bg-gray-50'"
          >
            <input type="radio" :value="r.v" v-model="promoteRole" class="text-blue-600" />
            <span class="text-sm text-gray-700">{{ r.label }}</span>
          </label>
        </div>
        <div class="flex gap-2 justify-end">
          <button @click="showPromoteModal = false" class="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg">
            取消
          </button>
          <button @click="confirmPromote" class="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700">
            确认
          </button>
        </div>
      </div>
    </div>
  </div>
</template>