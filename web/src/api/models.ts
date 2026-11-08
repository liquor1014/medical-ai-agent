import { apiGet, apiPost } from './http'
import type {
  ModelHealth,
  ModelLogsResponse,
  ModelTestResult
} from '@/types/api'

export function getModelHealth(): Promise<ModelHealth> {
  return apiGet<ModelHealth>('/models/health')
}

export function getModelLogs(limit = 50): Promise<ModelLogsResponse> {
  return apiGet<ModelLogsResponse>('/models/logs', { params: { limit } })
}

export function resetModelRoutes(): Promise<{ ok: boolean; routes: Record<string, string[]> }> {
  return apiPost<{ ok: boolean; routes: Record<string, string[]> }>('/models/switch', {
    reset: true
  })
}

export interface ModelTestPayload {
  task: string
  question: string
}

export function testModel(payload: ModelTestPayload): Promise<ModelTestResult> {
  return apiPost<ModelTestResult>('/models/test', payload, { timeout: 120000 })
}
