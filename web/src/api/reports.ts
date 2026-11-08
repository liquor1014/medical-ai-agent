import { apiGet, downloadFile } from './http'
import type { ReportDetail, ReportSummary } from '@/types/api'

export function listReports(): Promise<ReportSummary[]> {
  return apiGet<ReportSummary[]>('/reports')
}

export function getReport(id: number): Promise<ReportDetail> {
  return apiGet<ReportDetail>(`/reports/${id}`)
}

export function exportReport(id: number): Promise<void> {
  return downloadFile(`/reports/${id}/export`, `report-${id}.csv`)
}
