import { apiGet, apiPost } from './http'
import type { LoginResult, TenantOption } from '@/types/api'

export interface RegisterPayload {
  username: string
  password: string
  displayName?: string
}

export function login(username: string, password: string): Promise<LoginResult> {
  return apiPost<LoginResult>('/auth/login', { username, password })
}

export function register(payload: RegisterPayload): Promise<LoginResult> {
  return apiPost<LoginResult>('/auth/register', payload)
}

export function logout(): Promise<void> {
  return apiPost<void>('/auth/logout')
}

export function fetchTenants(): Promise<TenantOption[]> {
  return apiGet<TenantOption[]>('/tenants/list')
}
