import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '@/stores/user'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('@/views/HomeView.vue'),
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { public: true },
    },
    {
      path: '/register',
      name: 'register',
      component: () => import('@/views/RegisterView.vue'),
      meta: { public: true },
    },
    {
      path: '/setup',
      name: 'setup',
      component: () => import('@/views/InterviewSetupView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/interview',
      name: 'interview',
      component: () => import('@/views/InterviewView.vue'),
      meta: { bare: true, requiresAuth: true },
    },
    {
      path: '/chat',
      name: 'chat',
      component: () => import('@/views/ChatView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/code',
      name: 'code',
      component: () => import('@/views/CodePracticeView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/report/:id',
      name: 'report',
      component: () => import('@/views/ReportView.vue'),
      props: true,
      meta: { requiresAuth: true },
    },
    {
      path: '/interview/:interviewId/playback',
      name: 'interview-playback',
      component: () => import('@/views/RecordingPlaybackView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/share/:token',
      name: 'share',
      component: () => import('@/views/SharedReportView.vue'),
      props: true,
      meta: { public: true },
    },
    {
      path: '/resume/:id/report',
      name: 'resume-report',
      component: () => import('@/views/ResumeReportView.vue'),
      props: true,
      meta: { requiresAuth: true },
    },
    {
      path: '/history',
      name: 'history',
      component: () => import('@/views/HistoryView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/metrics',
      name: 'metrics',
      component: () => import('@/views/MetricsView.vue'),
      meta: { requiresAuth: true, requiresEnterprise: true },
    },
    {
      path: '/org',
      name: 'org',
      component: () => import('@/views/OrgView.vue'),
      meta: { requiresAuth: true, requiresEnterprise: true },
    },
    {
      path: '/invite/:token',
      name: 'invite',
      component: () => import('@/views/InviteEntryView.vue'),
      meta: { public: true, bare: true },
    },
    {
      path: '/profile',
      name: 'profile',
      component: () => import('@/views/ProfileView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('@/views/SettingsView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/admin',
      name: 'admin',
      component: () => import('@/views/AdminView.vue'),
      meta: { requiresAuth: true, requiresAdmin: true },
    },
  ],
})

// 路由守卫：数据路由需登录，分享报告（带 token query）公开访问；
// 企业侧路由（企业控制台 / 实测指标）额外要求企业身份
router.beforeEach(async (to) => {
  if (to.meta.requiresAuth) {
    if (to.name === 'report' && to.query.token) return true
    const userStore = useUserStore()
    if (!userStore.isLoggedIn) {
      return { path: '/login', query: { redirect: to.fullPath } }
    }
    // 刷新页面时用户信息尚未加载，先补一次，避免企业侧路由被误判为无权限
    if (!userStore.user) await userStore.fetchMe()
    if (to.meta.requiresEnterprise && !userStore.isEnterprise) {
      return { path: '/settings', query: { needEnterprise: '1' } }
    }
  }
  // 管理页允许已登录用户访问，密码验证由 AdminView 组件内部处理
  // 管理员角色用户可跳过密码验证
})

export default router
