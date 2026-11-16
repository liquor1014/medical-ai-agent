import { ref } from 'vue'

const TOKEN_KEY = 'medical_ai_token'
const USER_KEY = 'medical_ai_user'
const TENANT_KEY = 'medical_ai_tenant'
const ROLE_KEY = 'medical_ai_role'
const PERMISSIONS_KEY = 'medical_ai_permissions'

/** 系统超级管理员账号（硬编码，唯一拥有 super_admin 角色） */
export const SUPER_ADMIN_USERNAME = 'superAdmin'

export const DEFAULT_TENANT = 'hospital-demo'

/** 响应式权限码集合，供菜单动态渲染 */
export const permissions = ref<string[]>([])

export function getToken(): string {
  return localStorage.getItem(TOKEN_KEY) || ''
}

export function getUsername(): string {
  return localStorage.getItem(USER_KEY) || ''
}

export function getTenant(): string {
  return localStorage.getItem(TENANT_KEY) || DEFAULT_TENANT
}

export function getRole(): string {
  return localStorage.getItem(ROLE_KEY) || ''
}

export function getPermissions(): string[] {
  return permissions.value.length > 0 ? permissions.value : JSON.parse(localStorage.getItem(PERMISSIONS_KEY) || '[]')
}

export function setPermissions(perms: string[]): void {
  permissions.value = perms || []
  localStorage.setItem(PERMISSIONS_KEY, JSON.stringify(perms || []))
}

export function isSuperAdmin(): boolean {
  return getRole() === 'super_admin'
}

export function isTenantAdmin(): boolean {
  return getRole() === 'tenant_admin'
}

/** 是否拥有指定权限码（super_admin 全放行） */
export function hasPermission(code: string): boolean {
  if (isSuperAdmin()) return true
  return getPermissions().includes(code)
}

/** 是否拥有用户管理权限 */
export function canManageUsers(): boolean {
  return isSuperAdmin() || hasPermission('system:user')
}

/** 是否拥有角色配置管理权限 */
export function canManageRoles(): boolean {
  return isSuperAdmin() || hasPermission('system:role')
}

/**
 * 从后端重新拉取当前用户的权限码并刷新响应式状态
 * 用于角色/权限变更后无需刷新页面即可同步菜单
 */
export async function refreshPermissions(): Promise<void> {
  const { apiGet } = await import('@/api/http')
  try {
    const perms = await apiGet<string[]>('/auth/permissions')
    setPermissions(perms)
  } catch {
    // 拉取失败时保持现有权限
  }
}

export function saveSession(
  token: string,
  username: string,
  role = 'doctor',
  tenantId = DEFAULT_TENANT,
  perms: string[] = []
): void {
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.setItem(USER_KEY, username)
  localStorage.setItem(ROLE_KEY, role)
  localStorage.setItem(TENANT_KEY, tenantId)
  setPermissions(perms)
}

export function setTenant(tenantId: string): void {
  localStorage.setItem(TENANT_KEY, tenantId)
}

export function clearAuth(): void {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
  localStorage.removeItem(ROLE_KEY)
  localStorage.removeItem(PERMISSIONS_KEY)
  permissions.value = []
}

export function isLoggedIn(): boolean {
  return Boolean(getToken())
}
