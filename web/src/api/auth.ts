import { apiPost, apiGet } from './http'
import type { ForgotCodeResult, LoginResult, PasswordPolicy, TenantOption } from '@/types/api'

export interface RegisterPayload {
  username: string
  password: string
  displayName?: string
  email?: string
  tenantId?: string
}

export interface ForgotCodePayload {
  tenantId: string
  username: string
  email: string
}

export interface VerifyCodePayload extends ForgotCodePayload {
  code: string
}

export interface ResetPasswordPayload {
  tenantId: string
  username: string
  resetTicket: string
  newPassword: string
}

export function login(username: string, password: string, tenantId?: string): Promise<LoginResult> {
  return apiPost<LoginResult>('/auth/login', { username, password, tenantId })
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

export function fetchPasswordPolicy(): Promise<PasswordPolicy> {
  return apiGet<PasswordPolicy>('/auth/password/policy')
}

export function sendResetCode(payload: ForgotCodePayload): Promise<ForgotCodeResult> {
  return apiPost<ForgotCodeResult>('/auth/password/forgot-code', payload)
}

export function verifyResetCode(payload: VerifyCodePayload): Promise<string> {
  return apiPost<string>('/auth/password/verify-code', payload)
}

export function resetPassword(payload: ResetPasswordPayload): Promise<void> {
  return apiPost<void>('/auth/password/reset', payload)
}

export function changePassword(oldPassword: string, newPassword: string): Promise<void> {
  return apiPost<void>('/auth/password/change', { oldPassword, newPassword })
}
