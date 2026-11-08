export interface ApiResult<T> {
  code: number
  message: string
  data: T
}

export interface LoginResult {
  token: string
  username: string
}

export interface TenantOption {
  id: string
  name: string
}

export interface DocumentItem {
  id: number
  tenantId: string
  fileName: string
  objectKey: string
  docType: string
  status: string
  pageCount: number
  chunkCount: number
  createdAt: string
}

export interface FileUploadResult {
  id: number
  fileName: string
  status: string
}

export interface ReportSummary {
  id: number
  question: string
  status: string
  chartType: string | null
  rowCount: number
  createdAt: string
}

export interface ReportDetail extends ReportSummary {
  sql: string | null
  columns: string[]
  rows: Record<string, unknown>[]
}

export interface Citation {
  id?: number
  doc_id?: number
  page_no?: number
  section?: string | null
  content?: string
  type?: string
  report_id?: number
  title?: string
  row_count?: number
}

export interface SqlResult {
  columns: string[]
  rows: Record<string, unknown>[]
  row_count: number
  status: string
}

export interface ReportPayload extends SqlResult {
  report_id: number | null
  title: string
  chart_type: string
  option: Record<string, unknown>
  summary: string
}

export interface ModelInfo {
  provider: string
  model: string
}

export interface ReviewPayload {
  passed: boolean | null
  level?: string
  issues: string[]
  answer?: string
  model?: ModelInfo | null
}

export type ChatMessageStatus = 'streaming' | 'done' | 'error' | 'stopped'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  status: ChatMessageStatus
  createdAt: number
  intent?: string
  retrievalCount?: number
  citations: Citation[]
  sql?: string
  result?: SqlResult
  report?: ReportPayload
  review?: ReviewPayload
  model?: ModelInfo
  error?: string
}

export interface AuditLogItem {
  id: number
  tenantId: string
  userId: number
  action: string
  sqlHash: string | null
  result: string | null
  createdAt: string
}

export interface AuditPage {
  items: AuditLogItem[]
  total: number
  page: number
  size: number
  counts: Record<string, number>
  last24h: number
  actions: string[]
}

export interface LatencyStats {
  count: number
  mean: number
  p50: number
  p95: number
  max: number
}

export interface EvalMeta {
  run_id: string
  created_at: string
  dataset: string
  dataset_sha256: string
  dataset_items: number
  top_k: number
  tenant_ids: string[]
  python: string
  model_routes: Record<string, string>
  models_seen: string[]
}

export interface EvalSummary {
  item_count: number
  recall_at_5: number
  retrieval_hit_rate_at_5: number
  sql_execution_accuracy: number
  answer_accuracy: number
  answer_mean_keyword_coverage: number
  diagnostic_recall_at_5_by_keyword_overlap: number
  routing_accuracy: Record<string, number>
  latency_ms: LatencyStats
  latency_by_type_ms: Record<string, LatencyStats>
  passed_by_type: Record<string, number>
  failed_by_type: Record<string, number>
}

export interface EvalItem {
  id: string
  type: 'retrieval' | 'sql' | 'answer' | string
  question: string
  passed: boolean
  score: number
  latency_ms: number
  model?: string
  error?: string
  detail: Record<string, any>
}

export interface EvalReport {
  meta: EvalMeta
  summary: EvalSummary
  items: EvalItem[]
}

export interface EvalItemsQuery {
  keyword?: string
  type?: string
  result?: string
  page?: number
  size?: number
}

export interface EvalItemsPage {
  items: EvalItem[]
  total: number
  page: number
  size: number
  keyword?: string
  type?: string
  result?: string
}

export interface ModelProvider {
  name: string
  model: string
  base_url: string
  configured: boolean
  api_key: string
}

export interface ModelStat {
  provider: string
  status: string
  calls: number
  avg_latency_ms: number
  tokens: number
  cost: number
}

export interface ModelCallLog {
  provider: string
  model: string
  task_type: string
  status: string
  latency_ms: number
  first_token_ms?: number | null
  tokens: number
  cost: number
  error?: string | null
  trace_id?: string | null
  created_at: string
}

export interface ModelHealth {
  mock_mode: boolean
  timeout_seconds: number
  stream_idle_timeout: number
  routes: Record<string, string[]>
  providers: ModelProvider[]
  log_to_db: boolean
  stats_24h: ModelStat[]
  recent: ModelCallLog[]
}

export interface ModelLogsResponse {
  source: string
  count: number
  logs: ModelCallLog[]
}

export interface ModelTestAttempt {
  provider?: string
  status?: string
  latency_ms?: number
  error?: string
}

export interface ModelTestResult {
  text: string
  provider: string
  model: string
  latency_ms: number
  first_token_ms?: number | null
  prompt_tokens: number
  completion_tokens: number
  tokens: number
  cost: number
  degraded: boolean
  attempts: ModelTestAttempt[]
}
