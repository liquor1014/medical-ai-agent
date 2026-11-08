import axios from 'axios'
import type { AxiosError, AxiosRequestConfig } from 'axios'

import { clearAuth, getTenant, getToken } from '@/store/auth'
import type { ApiResult } from '@/types/api'

export class ApiError extends Error {
  code: number

  constructor(code: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.code = code
  }
}

export const http = axios.create({
  baseURL: '/api',
  timeout: 60000
})

http.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers.set('Authorization', `Bearer ${token}`)
  }
  config.headers.set('X-Tenant-Id', getTenant())
  return config
})

function redirectToLogin(): void {
  clearAuth()
  if (window.location.pathname !== '/login') {
    const redirect = encodeURIComponent(window.location.pathname + window.location.search)
    window.location.href = `/login?redirect=${redirect}`
  }
}

export async function request<T>(config: AxiosRequestConfig): Promise<T> {
  try {
    const res = await http.request<ApiResult<T>>(config)
    const body = res.data
    if (body && typeof body === 'object' && 'code' in body) {
      if (body.code === 200) {
        return body.data
      }
      if (body.code === 401) {
        redirectToLogin()
      }
      throw new ApiError(body.code, body.message || '请求失败')
    }
    return body as unknown as T
  } catch (error) {
    if (error instanceof ApiError) {
      throw error
    }
    const err = error as AxiosError<ApiResult<unknown>>
    if (err.response?.status === 401) {
      redirectToLogin()
      throw new ApiError(401, '登录已过期，请重新登录')
    }
    const message = err.response?.data?.message || err.message || '网络请求失败'
    throw new ApiError(err.response?.status ?? 500, message)
  }
}

export function apiGet<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
  return request<T>({ ...config, url, method: 'GET' })
}

export function apiPost<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
  return request<T>({ ...config, url, method: 'POST', data })
}

export function apiDelete<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
  return request<T>({ ...config, url, method: 'DELETE' })
}

export async function downloadFile(url: string, filename: string): Promise<void> {
  try {
    const res = await http.get(url, { responseType: 'blob' })
    const blob = res.data as Blob
    const objectUrl = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = objectUrl
    link.download = filename
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(objectUrl)
  } catch (error) {
    const err = error as AxiosError<Blob>
    throw new ApiError(err.response?.status ?? 500, '导出失败，请稍后重试')
  }
}
