const TOKEN_KEY = 'medical_ai_token'
const USER_KEY = 'medical_ai_user'
const TENANT_KEY = 'medical_ai_tenant'

export const DEFAULT_TENANT = 'hospital-demo'

export function getToken(): string {
  return localStorage.getItem(TOKEN_KEY) || ''
}

export function getUsername(): string {
  return localStorage.getItem(USER_KEY) || ''
}

export function getTenant(): string {
  return localStorage.getItem(TENANT_KEY) || DEFAULT_TENANT
}

export function saveSession(token: string, username: string): void {
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.setItem(USER_KEY, username)
  if (!localStorage.getItem(TENANT_KEY)) {
    localStorage.setItem(TENANT_KEY, DEFAULT_TENANT)
  }
}

export function setTenant(tenantId: string): void {
  localStorage.setItem(TENANT_KEY, tenantId)
}

export function clearAuth(): void {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}

export function isLoggedIn(): boolean {
  return Boolean(getToken())
}
