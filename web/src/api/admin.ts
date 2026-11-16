import { apiGet, apiPost, apiDelete } from './http'
import type { TenantUser } from '@/types/api'

/**
 * 列出指定租户下的全部用户及其角色
 * super_admin 可通过 tenantId 跨租户查看；tenant_admin 仅本租户
 */
export function listTenantUsers(tenantId?: string): Promise<TenantUser[]> {
  const params = tenantId ? { tenantId } : undefined
  return apiGet<TenantUser[]>('/admin/users', { params })
}

/**
 * 为用户在指定租户下分配 / 修改角色
 */
export function assignRole(userId: number, role: string, tenantId?: string): Promise<void> {
  return apiPost<void>('/admin/users/role', { userId, role, tenantId })
}

/**
 * 解除用户与租户的绑定
 */
export function unbindUser(userId: number, tenantId?: string): Promise<void> {
  const params: Record<string, unknown> = { userId }
  if (tenantId) params.tenantId = tenantId
  return apiDelete<void>('/admin/users', { params })
}
