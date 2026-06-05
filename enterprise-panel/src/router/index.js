import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const routes = [
  {
    path: '/enterprise/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
    meta: { public: true }
  },
  {
    path: '/enterprise',
    component: () => import('../components/AppLayout.vue'),
    children: [
      { path: '', name: 'Dashboard', component: () => import('../views/Dashboard.vue') },
      { path: 'members', name: 'Members', component: () => import('../views/Members.vue') },
      { path: 'members/:id', name: 'MemberDetail', component: () => import('../views/MemberDetail.vue') },
      { path: 'activities', name: 'Activities', component: () => import('../views/Activities.vue') },
      { path: 'activities/:id', name: 'ActivityDetail', component: () => import('../views/ActivityDetail.vue') },
      { path: 'sessions', name: 'Sessions', component: () => import('../views/Sessions.vue') },
      { path: 'invite-codes', name: 'InviteCodes', component: () => import('../views/InviteCodes.vue') },
      { path: 'settings', name: 'Settings', component: () => import('../views/Settings.vue') },
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (!to.meta.public && !auth.token) {
    return { name: 'Login' }
  }
})

export default router
