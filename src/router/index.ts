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
      path: '/admin',
      name: 'admin',
      component: () => import('@/views/AdminView.vue'),
    },
  ],
})

// 路由守卫：数据路由需登录，分享报告（带 token query）公开访问
router.beforeEach((to) => {
  if (to.meta.requiresAuth) {
    // 分享报告通过 token query 公开访问
    if (to.name === 'report' && to.query.token) return true
    const userStore = useUserStore()
    if (!userStore.isLoggedIn) {
      return { path: '/login', query: { redirect: to.fullPath } }
    }
  }
})

export default router
