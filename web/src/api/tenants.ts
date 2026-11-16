import { apiDelete, apiGet, apiPost, apiPut } from './http'
import type { TenantItem, TenantPayload } from '@/types/api'

export function fetchTenantAdminList(): Promise<TenantItem[]> {
  return apiGet<TenantItem[]>('/tenants/admin/list')
}

export function createTenant(payload: TenantPayload): Promise<TenantItem> {
  return apiPost<TenantItem>('/tenants/admin', payload)
}

export function updateTenant(id: string, payload: TenantPayload): Promise<TenantItem> {
  return apiPut<TenantItem>(`/tenants/admin/${encodeURIComponent(id)}`, payload)
}

export function deleteTenant(id: string): Promise<void> {
  return apiDelete<void>(`/tenants/admin/${encodeURIComponent(id)}`)
}
