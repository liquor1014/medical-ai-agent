import { apiGet } from './http'
import type { EvalItemsPage, EvalItemsQuery, EvalReport } from '@/types/api'

export function getEvalReport(): Promise<EvalReport> {
  return apiGet<EvalReport>('/eval/latest')
}

export function getEvalItems(
  query: EvalItemsQuery,
  signal?: AbortSignal
): Promise<EvalItemsPage> {
  return apiGet<EvalItemsPage>('/eval/items', {
    params: {
      keyword: query.keyword?.trim() || undefined,
      type: query.type || undefined,
      result: query.result || undefined,
      page: query.page ?? 1,
      size: query.size ?? 10
    },
    signal
  })
}
