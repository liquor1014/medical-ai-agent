import { apiGet, apiPost, apiPut, apiDelete, apiPatch } from './http'
import type { RoleConfig } from '@/types/api'

export function listRoles(): Promise<RoleConfig[]> {
  return apiGet<RoleConfig[]>('/roles')
}

export function createRole(data: { code: string; name: string; description?: string }): Promise<RoleConfig> {
  return apiPost<RoleConfig>('/roles', data)
}

export function updateRole(code: string, data: { name: string; description?: string }): Promise<RoleConfig> {
  return apiPut<RoleConfig>(`/roles/${code}`, data)
}

export function deleteRole(code: string): Promise<void> {
  return apiDelete<void>(`/roles/${code}`)
}

export function toggleRoleStatus(code: string, status: string): Promise<RoleConfig> {
  return apiPatch<RoleConfig>(`/roles/${code}/status`, { status })
}
