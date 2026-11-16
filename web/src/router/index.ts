import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

import { getToken, isSuperAdmin, canManageUsers, canManageRoles } from '@/store/auth'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { title: '登录' }
  },
  {
    path: '/',
    component: () => import('@/layouts/AppLayout.vue'),
    redirect: '/files',
    children: [
      {
        path: 'files',
        name: 'files',
        component: () => import('@/views/FilesView.vue'),
        meta: { title: '文件库' }
      },
      {
        path: 'chat',
        name: 'chat',
        component: () => import('@/views/ChatView.vue'),
        meta: { title: '智能问答' }
      },
      {
        path: 'reports',
        name: 'reports',
        component: () => import('@/views/ReportsView.vue'),
        meta: { title: '报表中心' }
      },
      {
        path: 'audit',
        name: 'audit',
        component: () => import('@/views/AuditView.vue'),
        meta: { title: '审计日志' }
      },
      {
        path: 'eval',
        name: 'eval',
        component: () => import('@/views/EvalView.vue'),
        meta: { title: '评测看板' }
      },
      {
        path: 'models',
        name: 'models',
        component: () => import('@/views/ModelView.vue'),
        meta: { title: '模型健康' }
      },
      {
        path: 'tenants',
        name: 'tenants',
        component: () => import('@/views/TenantAdminView.vue'),
        meta: { title: '租户管理', requiresAdmin: true }
      },
      {
        path: 'users',
        name: 'users',
        component: () => import('@/views/UserAdminView.vue'),
        meta: { title: '用户管理', requiresUserManage: true }
      },
      {
        path: 'roles',
        name: 'roles',
        component: () => import('@/views/RoleConfigView.vue'),
        meta: { title: '角色配置', requiresRoleManage: true }
      }
    ]
  },
  {
    path: '/403',
    name: 'forbidden',
    component: () => import('@/views/ForbiddenView.vue'),
    meta: { title: '无访问权限' }
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('@/views/NotFoundView.vue'),
    meta: { title: '页面不存在' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to) => {
  const token = getToken()
  if (to.path === '/login') {
    return token ? { path: '/files' } : true
  }
  if (!token) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  if (to.meta.requiresAdmin && !isSuperAdmin()) {
    return { path: '/403' }
  }
  if (to.meta.requiresUserManage && !canManageUsers()) {
    return { path: '/403' }
  }
  if (to.meta.requiresRoleManage && !canManageRoles()) {
    return { path: '/403' }
  }
  return true
})

router.afterEach((to) => {
  const title = to.meta.title as string | undefined
  document.title = title ? `${title} · 医疗 AI Agent` : '医疗 AI Agent'
})

export default router
