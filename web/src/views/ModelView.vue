<template>
  <div class="model-page page-block">
    <div class="page-head">
      <div>
        <h2>模型健康</h2>
        <p class="muted">
          模型提供者配置、任务路由与降级链路；调用统计来自 model_call_log（全局运维数据，不区分租户）。
        </p>
      </div>
      <div class="head-actions">
        <span class="muted updated-at">更新于 {{ lastUpdated || '-' }}</span>
        <el-button :icon="Refresh" :loading="loading" @click="refreshAll">刷新</el-button>
        <el-button type="primary" :icon="VideoPlay" @click="openTest">试调用</el-button>
      </div>
    </div>

    <el-alert
      v-if="errorMessage"
      type="error"
      :closable="false"
      show-icon
      :title="errorMessage"
      class="error-alert"
    >
      <template #default>
        <el-button size="small" @click="refreshAll">重新加载</el-button>
      </template>
    </el-alert>

    <template v-if="health">
      <el-alert
        v-if="health.mock_mode"
        type="warning"
        :closable="false"
        show-icon
        title="当前为 Mock 模式：问答不会调用真实模型，仅用于离线演示"
        class="mock-alert"
      />

      <div class="stat-grid">
        <div class="stat-card panel">
          <span class="stat-label">运行模式</span>
          <span class="stat-value" :class="{ warning: health.mock_mode }">
            {{ health.mock_mode ? 'Mock' : '真实模型' }}
          </span>
          <span class="stat-sub muted">超时 {{ health.timeout_seconds }}s · 流空闲 {{ health.stream_idle_timeout }}s</span>
        </div>
        <div class="stat-card panel">
          <span class="stat-label">提供者</span>
          <span class="stat-value">{{ health.providers.length }}</span>
          <span class="stat-sub muted">{{ configuredCount }} 个已配置 · {{ health.routes.chat?.[0] || '-' }} 为首选</span>
        </div>
        <div class="stat-card panel">
          <span class="stat-label">24h 调用</span>
          <span class="stat-value">{{ calls24h }}</span>
          <span class="stat-sub muted">平均 {{ avgLatency24h }} ms · {{ errors24h }} 次失败/降级</span>
        </div>
        <div class="stat-card panel">
          <span class="stat-label">24h 成本</span>
          <span class="stat-value cost">${{ cost24h.toFixed(4) }}</span>
          <span class="stat-sub muted">{{ tokens24h.toLocaleString() }} tokens</span>
        </div>
      </div>

      <div class="two-col">
        <section class="panel provider-panel">
          <div class="card-title panel-title">
            <span>模型提供者</span>
            <span class="muted">{{ health.log_to_db ? '调用日志已落库' : '仅内存日志' }}</span>
          </div>

          <div class="provider-list">
            <div
              v-for="provider in health.providers"
              :key="provider.name"
              class="provider-card"
              :class="{ primary: primaryProviders.has(provider.name), inactive: !isInAnyRoute(provider.name) }"
            >
              <div class="provider-head">
                <span class="provider-name">{{ provider.name }}</span>
                <div class="provider-tags">
                  <el-tag v-if="primaryProviders.has(provider.name)" size="small" type="success" effect="light">
                    首选
                  </el-tag>
                  <el-tag v-else-if="isInAnyRoute(provider.name)" size="small" effect="plain">备用</el-tag>
                  <el-tag v-else size="small" type="info" effect="plain">未启用</el-tag>
                  <el-tag :type="provider.configured ? 'success' : 'danger'" size="small" effect="plain">
                    {{ provider.configured ? '已配置' : '缺少 Key' }}
                  </el-tag>
                </div>
              </div>
              <div class="provider-model">{{ provider.model }}</div>
              <div class="provider-meta">
                <span class="mono">{{ provider.base_url }}</span>
                <span class="mono">{{ provider.api_key }}</span>
              </div>
              <div class="provider-stats muted">
                <template v-if="providerStats(provider.name)">
                  24h {{ providerStats(provider.name)?.calls }} 次 · 平均
                  {{ providerStats(provider.name)?.avg }} ms · 失败
                  {{ providerStats(provider.name)?.errors }} 次
                </template>
                <template v-else>近 24h 暂无调用</template>
              </div>
            </div>
          </div>
        </section>

        <section class="panel route-panel">
          <div class="card-title panel-title">
            <span>任务路由与降级</span>
            <el-popconfirm
              title="恢复环境变量中的默认路由？当前运行时切换将失效。"
              confirm-button-text="恢复默认"
              cancel-button-text="取消"
              width="280"
              @confirm="resetRoutes"
            >
              <template #reference>
                <el-button link type="primary" size="small">恢复默认路由</el-button>
              </template>
            </el-popconfirm>
          </div>

          <div class="route-list">
            <div v-for="(providers, task) in health.routes" :key="task" class="route-row">
              <span class="route-task">{{ taskLabel(String(task)) }}</span>
              <div class="route-chain">
                <template v-for="(provider, index) in providers" :key="`${task}-${provider}`">
                  <el-tag
                    :type="index === 0 ? 'success' : 'info'"
                    :effect="index === 0 ? 'light' : 'plain'"
                    size="small"
                  >
                    {{ index + 1 }}. {{ provider }}
                  </el-tag>
                  <el-icon v-if="index < providers.length - 1" class="route-arrow">
                    <Right />
                  </el-icon>
                </template>
              </div>
            </div>
          </div>

          <p class="route-note muted">
            调用按顺序尝试，失败自动降级到下一个提供者；运行时切换仅内存生效，重启后回到环境变量配置。
          </p>

          <div class="stats-title">24 小时调用明细</div>
          <el-table :data="health.stats_24h" size="small" max-height="220" class="stats-table">
            <el-table-column label="提供者" prop="provider" min-width="100" />
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag size="small" :type="statusMeta(row.status).type" effect="plain">
                  {{ statusMeta(row.status).label }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="调用" prop="calls" width="70" align="right" />
            <el-table-column label="平均延迟" width="95" align="right">
              <template #default="{ row }">{{ row.avg_latency_ms }} ms</template>
            </el-table-column>
            <el-table-column label="Tokens" prop="tokens" width="90" align="right" />
            <el-table-column label="成本" width="90" align="right">
              <template #default="{ row }">${{ row.cost.toFixed(4) }}</template>
            </el-table-column>
            <template #empty>
              <el-empty description="近 24 小时暂无调用记录" :image-size="56" />
            </template>
          </el-table>
        </section>
      </div>

      <section class="panel log-panel">
        <div class="card-title panel-title">
          <span>最近调用日志</span>
          <div class="log-actions">
            <el-select v-model="logLimit" size="small" class="limit-select" @change="loadLogs">
              <el-option label="20 条" :value="20" />
              <el-option label="50 条" :value="50" />
              <el-option label="100 条" :value="100" />
            </el-select>
          </div>
        </div>

        <el-table v-loading="logsLoading" :data="logs" size="small" max-height="380">
          <el-table-column label="时间" width="160">
            <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="提供者 / 模型" min-width="170">
            <template #default="{ row }">
              <div class="log-model">
                <span>{{ row.provider }}</span>
                <span class="muted">{{ row.model }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="任务" width="100">
            <template #default="{ row }">{{ taskLabel(row.task_type) }}</template>
          </el-table-column>
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag size="small" :type="statusMeta(row.status).type" effect="light">
                {{ statusMeta(row.status).label }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="延迟" width="95" align="right">
            <template #default="{ row }">
              {{ row.latency_ms ?? '-' }} ms
            </template>
          </el-table-column>
          <el-table-column label="Tokens" width="90" align="right" prop="tokens" />
          <el-table-column label="成本" width="90" align="right">
            <template #default="{ row }">${{ (row.cost ?? 0).toFixed(4) }}</template>
          </el-table-column>
          <el-table-column label="错误" min-width="180" show-overflow-tooltip>
            <template #default="{ row }">
              <span v-if="row.error" class="error-text">{{ row.error }}</span>
              <span v-else class="muted">-</span>
            </template>
          </el-table-column>
          <template #empty>
            <el-empty description="暂无模型调用日志，先在智能问答发起一次提问" :image-size="64" />
          </template>
        </el-table>
      </section>
    </template>

    <div v-else-if="!loading && errorMessage" class="panel empty-panel">
      <el-empty description="模型服务信息加载失败" :image-size="88">
        <el-button type="primary" @click="refreshAll">重试</el-button>
      </el-empty>
    </div>

    <el-dialog v-model="testVisible" title="模型试调用" width="620px">
      <el-form label-position="top">
        <el-form-item label="任务路由">
          <el-select v-model="testForm.task" class="task-select">
            <el-option label="对话 Chat" value="chat" />
            <el-option label="数据查询 NL2SQL" value="nl2sql" />
            <el-option label="报表 Report" value="report" />
          </el-select>
        </el-form-item>
        <el-form-item label="测试问题">
          <el-input
            v-model="testForm.question"
            type="textarea"
            :autosize="{ minRows: 2, maxRows: 4 }"
            placeholder="输入一个简短问题，走完整路由与降级链路"
          />
        </el-form-item>
      </el-form>

      <div v-if="testResult" class="test-result">
        <div class="test-tags">
          <el-tag type="success" effect="light">{{ testResult.provider }}</el-tag>
          <el-tag effect="plain">{{ testResult.model }}</el-tag>
          <el-tag type="info" effect="plain">{{ testResult.latency_ms }} ms</el-tag>
          <el-tag type="info" effect="plain">{{ testResult.tokens }} tokens</el-tag>
          <el-tag type="info" effect="plain">${{ testResult.cost.toFixed(4) }}</el-tag>
          <el-tag v-if="testResult.degraded" type="warning" effect="light">发生降级</el-tag>
        </div>
        <div class="test-answer">{{ testResult.text }}</div>
        <div v-if="testResult.attempts?.length" class="test-attempts muted">
          尝试链路：
          <span v-for="(attempt, index) in testResult.attempts" :key="index" class="attempt-item">
            {{ index + 1 }}. {{ attempt.provider || 'unknown' }}
            <em>{{ attempt.status || 'unknown' }}</em>
            <span v-if="attempt.error"> · {{ attempt.error }}</span>
          </span>
        </div>
      </div>

      <template #footer>
        <el-button @click="testVisible = false">关闭</el-button>
        <el-button type="primary" :loading="testing" @click="runTest">开始试调用</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Right, VideoPlay } from '@element-plus/icons-vue'

import {
  getModelHealth,
  getModelLogs,
  resetModelRoutes,
  testModel
} from '@/api/models'
import { formatDateTime } from '@/utils/format'
import type {
  ModelCallLog,
  ModelHealth,
  ModelTestResult
} from '@/types/api'

const loading = ref(false)
const logsLoading = ref(false)
const health = ref<ModelHealth | null>(null)
const logs = ref<ModelCallLog[]>([])
const logLimit = ref(50)
const errorMessage = ref('')
const lastUpdated = ref('')
const testVisible = ref(false)
const testing = ref(false)
const testResult = ref<ModelTestResult | null>(null)

const testForm = reactive({
  task: 'chat',
  question: '用一句话说明当前使用的是哪个模型'
})

let timer: number | undefined
let healthFetching = false
let logsFetching = false

const configuredCount = computed(
  () => health.value?.providers.filter((provider) => provider.configured).length || 0
)

const primaryProviders = computed(() => {
  const set = new Set<string>()
  for (const providers of Object.values(health.value?.routes || {})) {
    if (providers.length > 0) set.add(providers[0])
  }
  return set
})

const calls24h = computed(() =>
  (health.value?.stats_24h || []).reduce((sum, stat) => sum + stat.calls, 0)
)

const errors24h = computed(() =>
  (health.value?.stats_24h || [])
    .filter((stat) => stat.status !== 'success' && stat.status !== 'ok')
    .reduce((sum, stat) => sum + stat.calls, 0)
)

const avgLatency24h = computed(() => {
  const stats = health.value?.stats_24h || []
  const totalCalls = calls24h.value
  if (!totalCalls) return 0
  const weighted = stats.reduce((sum, stat) => sum + stat.avg_latency_ms * stat.calls, 0)
  return Math.round(weighted / totalCalls)
})

const tokens24h = computed(() =>
  (health.value?.stats_24h || []).reduce((sum, stat) => sum + stat.tokens, 0)
)

const cost24h = computed(() =>
  (health.value?.stats_24h || []).reduce((sum, stat) => sum + stat.cost, 0)
)

onMounted(async () => {
  await refreshAll()
  timer = window.setInterval(() => {
    loadHealth(true)
    loadLogs(true)
  }, 30000)
})

onBeforeUnmount(() => {
  if (timer) window.clearInterval(timer)
})

async function refreshAll(): Promise<void> {
  await Promise.all([loadHealth(), loadLogs()])
}

async function loadHealth(silent = false): Promise<void> {
  if (healthFetching) return
  healthFetching = true
  if (!silent) loading.value = true
  try {
    health.value = await getModelHealth()
    errorMessage.value = ''
    lastUpdated.value = formatDateTime(new Date().toISOString())
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '模型健康信息加载失败'
  } finally {
    loading.value = false
    healthFetching = false
  }
}

async function loadLogs(silent = false): Promise<void> {
  if (logsFetching) return
  logsFetching = true
  if (!silent) logsLoading.value = true
  try {
    const data = await getModelLogs(logLimit.value)
    logs.value = data.logs
  } catch (error) {
    if (!silent) {
      ElMessage.error(error instanceof Error ? error.message : '模型调用日志加载失败')
    }
  } finally {
    logsLoading.value = false
    logsFetching = false
  }
}

function providerStats(name: string): { calls: number; avg: number; errors: number } | null {
  const stats = (health.value?.stats_24h || []).filter((stat) => stat.provider === name)
  if (stats.length === 0) return null
  const calls = stats.reduce((sum, stat) => sum + stat.calls, 0)
  const avg = Math.round(
    stats.reduce((sum, stat) => sum + stat.avg_latency_ms * stat.calls, 0) / Math.max(calls, 1)
  )
  const errors = stats
    .filter((stat) => stat.status !== 'success' && stat.status !== 'ok')
    .reduce((sum, stat) => sum + stat.calls, 0)
  return { calls, avg, errors }
}

function isInAnyRoute(name: string): boolean {
  return Object.values(health.value?.routes || {}).some((providers) => providers.includes(name))
}

function taskLabel(task: string): string {
  const map: Record<string, string> = {
    chat: '对话',
    nl2sql: '数据查询',
    report: '报表生成',
    retrieval: '检索'
  }
  return map[task] || task
}

function statusMeta(status: string): { label: string; type: 'success' | 'danger' | 'warning' | 'info' } {
  if (status === 'success' || status === 'ok') {
    return { label: '成功', type: 'success' }
  }
  if (status === 'error' || status === 'failed') {
    return { label: '失败', type: 'danger' }
  }
  if (status === 'fallback' || status === 'degraded') {
    return { label: '降级', type: 'warning' }
  }
  if (status === 'truncated') {
    return { label: '中断', type: 'warning' }
  }
  return { label: status || '未知', type: 'info' }
}

async function resetRoutes(): Promise<void> {
  try {
    await resetModelRoutes()
    ElMessage.success('已恢复默认路由')
    await refreshAll()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '恢复默认路由失败')
  }
}

function openTest(): void {
  testResult.value = null
  testVisible.value = true
}

async function runTest(): Promise<void> {
  if (!testForm.question.trim()) {
    ElMessage.warning('请输入测试问题')
    return
  }
  testing.value = true
  try {
    testResult.value = await testModel({
      task: testForm.task,
      question: testForm.question.trim()
    })
    ElMessage.success('试调用完成')
    await refreshAll()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '试调用失败')
  } finally {
    testing.value = false
  }
}
</script>

<style scoped>
.model-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.page-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.page-head h2 {
  margin: 0 0 6px;
  font-size: 20px;
}

.page-head p {
  margin: 0;
}

.head-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.updated-at {
  font-size: 12px;
}

.error-alert,
.mock-alert {
  margin: 0;
}

.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.stat-card {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 14px 16px;
}

.stat-label {
  font-size: 12px;
  color: var(--muted);
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
  line-height: 1.2;
  color: #15803d;
}

.stat-value.warning {
  color: #b45309;
}

.stat-value.cost {
  color: #1d4ed8;
}

.stat-sub {
  font-size: 12px;
}

.two-col {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 14px;
  align-items: stretch;
}

.provider-panel,
.route-panel {
  display: flex;
  flex-direction: column;
  padding: 14px 16px 16px;
}

.panel-title {
  margin-bottom: 12px;
}

.provider-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.provider-card {
  padding: 12px 14px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: #fbfcfe;
}

.provider-card.primary {
  border-color: #bfdbfe;
  background: #f5f9ff;
}

.provider-card.inactive {
  opacity: 0.72;
}

.provider-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.provider-name {
  font-size: 15px;
  font-weight: 700;
  color: var(--text);
}

.provider-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.provider-model {
  margin-top: 4px;
  font-size: 13px;
  color: #475569;
}

.provider-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 14px;
  margin-top: 6px;
  font-size: 11.5px;
  color: #94a3b8;
}

.mono {
  font-family: Consolas, 'Courier New', monospace;
}

.provider-stats {
  margin-top: 8px;
  font-size: 12px;
}

.route-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 10px;
}

.route-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: #fbfcfe;
}

.route-task {
  flex: none;
  width: 76px;
  font-size: 13px;
  font-weight: 600;
  color: #475569;
}

.route-chain {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}

.route-arrow {
  color: #94a3b8;
  font-size: 12px;
}

.route-note {
  margin: 0 0 12px;
  font-size: 12px;
  line-height: 1.6;
}

.stats-title {
  margin-bottom: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--muted);
}

.stats-table {
  width: 100%;
}

.log-panel {
  padding: 14px 16px 16px;
}

.log-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.limit-select {
  width: 100px;
}

.log-model {
  display: flex;
  flex-direction: column;
  line-height: 1.4;
}

.log-model .muted {
  font-size: 11.5px;
}

.error-text {
  color: #b91c1c;
  font-size: 12px;
}

.empty-panel {
  padding: 20px;
}

.task-select {
  width: 220px;
}

.test-result {
  padding: 12px 14px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: #fbfcfe;
}

.test-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 10px;
}

.test-answer {
  font-size: 13.5px;
  line-height: 1.75;
  color: var(--text);
  white-space: pre-wrap;
  word-break: break-word;
}

.test-attempts {
  margin-top: 10px;
  padding-top: 8px;
  border-top: 1px dashed var(--border);
  font-size: 12px;
}

.attempt-item {
  margin-right: 12px;
}

.attempt-item em {
  font-style: normal;
  color: #b45309;
}

@media (max-width: 1100px) {
  .stat-grid,
  .two-col {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 760px) {
  .stat-grid,
  .two-col {
    grid-template-columns: 1fr;
  }

  .updated-at {
    display: none;
  }
}
</style>
