import { apiGet } from './http'
import type { AuditPage } from '@/types/api'

export interface AuditQuery {
  page: number
  size: number
  action?: string
  result?: string
}

export function listAuditLogs(query: AuditQuery): Promise<AuditPage> {
  return apiGet<AuditPage>('/audit/logs', {
    params: {
      page: query.page,
      size: query.size,
      action: query.action || undefined,
      result: query.result || undefined
    }
  })
}
