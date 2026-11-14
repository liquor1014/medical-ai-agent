import { apiGet, apiPatch, apiPost, apiPut } from './http'
import type {
  ModelHealth,
  ModelLogsResponse,
  ModelProviderMutation,
  ModelProviderPayload,
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

export function createModelProvider(
  payload: ModelProviderPayload
): Promise<ModelProviderMutation> {
  return apiPost<ModelProviderMutation>('/models/providers', payload)
}

export function updateModelProvider(
  name: string,
  payload: ModelProviderPayload
): Promise<ModelProviderMutation> {
  return apiPut<ModelProviderMutation>(
    `/models/providers/${encodeURIComponent(name)}`,
    payload
  )
}

export function setModelProviderEnabled(
  name: string,
  enabled: boolean
): Promise<ModelProviderMutation> {
  return apiPatch<ModelProviderMutation>(
    `/models/providers/${encodeURIComponent(name)}/enabled`,
    { enabled }
  )
}
