<template>
  <div v-loading="loading" class="eval-page page-block">
    <div class="page-head">
      <div>
        <h2>评测看板</h2>
        <p class="muted">
          基于 eval_v1 测试集的回归评测：Recall@5、SQL 执行准确率、答案准确率与延迟分位；数据集为全局基准，不随租户切换。
        </p>
      </div>
      <el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button>
    </div>

    <div v-if="errorMessage" class="panel empty-panel">
      <el-empty :description="errorMessage" :image-size="88">
        <el-button type="primary" @click="load">重新加载</el-button>
      </el-empty>
      <p class="empty-hint muted">
        若尚无结果，请在 ai-service 目录运行
        <code>python -m app.eval.run_eval</code>
        生成最新评测文件。
      </p>
    </div>

    <template v-else-if="report">
      <div class="meta-bar panel">
        <span><b>Run</b> {{ report.meta.run_id }}</span>
        <span><b>时间</b> {{ report.meta.created_at }}</span>
        <span><b>数据集</b> {{ report.meta.dataset_items }} 条 · Top{{ report.meta.top_k }}</span>
        <span><b>模型</b> {{ report.meta.models_seen.join(', ') || '-' }}</span>
        <span class="meta-routes"><b>路由</b> {{ routeText }}</span>
        <el-tooltip :content="report.meta.dataset_sha256" placement="top">
          <span class="meta-sha"><b>SHA</b> {{ report.meta.dataset_sha256.slice(0, 12) }}…</span>
        </el-tooltip>
      </div>

      <div class="stat-grid">
        <div class="stat-card panel">
          <span class="stat-label">Recall@5</span>
          <span class="stat-value">{{ percent(report.summary.recall_at_5) }}</span>
          <span class="stat-sub muted">{{ typeStats.retrieval.passed }}/{{ typeStats.retrieval.total }} 条检索命中</span>
        </div>
        <div class="stat-card panel">
          <span class="stat-label">SQL 执行准确率</span>
          <span class="stat-value">{{ percent(report.summary.sql_execution_accuracy) }}</span>
          <span class="stat-sub muted">{{ typeStats.sql.passed }}/{{ typeStats.sql.total }} 条执行一致</span>
        </div>
        <div class="stat-card panel">
          <span class="stat-label">答案准确率</span>
          <span class="stat-value">{{ percent(report.summary.answer_accuracy) }}</span>
          <span class="stat-sub muted">{{ typeStats.answer.passed }}/{{ typeStats.answer.total }} 条答案命中 · 覆盖率 {{ percent(report.summary.answer_mean_keyword_coverage) }}</span>
        </div>
        <div class="stat-card panel">
          <span class="stat-label">P95 延迟</span>
          <span class="stat-value latency">{{ report.summary.latency_ms.p95.toFixed(0) }}<small>ms</small></span>
          <span class="stat-sub muted">均值 {{ report.summary.latency_ms.mean.toFixed(0) }} ms · 最大 {{ report.summary.latency_ms.max.toFixed(0) }} ms</span>
        </div>
      </div>

      <div class="chart-panel panel">
        <div class="card-title">
          <span>分类延迟（毫秒）</span>
          <span class="muted">{{ report.summary.item_count }} 条用例</span>
        </div>
        <EChart v-if="latencyOption" :option="latencyOption" height="260px" />
      </div>

      <div class="table-panel panel">
        <div class="table-toolbar">
          <el-select v-model="typeFilter" class="filter-select" @change="applyFilters">
            <el-option label="全部类型" value="" />
            <el-option label="文档检索" value="retrieval" />
            <el-option label="SQL 查询" value="sql" />
            <el-option label="答案生成" value="answer" />
          </el-select>
          <el-select v-model="resultFilter" class="filter-select" @change="applyFilters">
            <el-option label="全部结果" value="" />
            <el-option label="通过" value="passed" />
            <el-option label="失败" value="failed" />
          </el-select>
          <el-input
            v-model="keyword"
            class="search-input"
            placeholder="搜索用例问题"
            clearable
            :prefix-icon="Search"
            @input="onKeywordInput"
            @clear="applyFilters"
          />
          <span class="toolbar-count muted">{{ total }} 条</span>
        </div>

        <el-alert
          v-if="searchError"
          type="error"
          :closable="false"
          show-icon
          :title="searchError"
          class="search-alert"
        >
          <template #default>
            <el-button size="small" @click="loadItems">重试</el-button>
          </template>
        </el-alert>

        <el-table v-loading="itemsLoading" :data="items" class="eval-table" @row-click="openDetail">
          <el-table-column label="编号" width="80" prop="id" />
          <el-table-column label="类型" width="110">
            <template #default="{ row }">
              <el-tag size="small" effect="plain">{{ evalTypeLabel(row.type) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="用例问题" min-width="280" show-overflow-tooltip prop="question" />
          <el-table-column label="结果" width="90">
            <template #default="{ row }">
              <el-tag size="small" :type="row.passed ? 'success' : 'danger'" effect="light">
                {{ row.passed ? '通过' : '失败' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="得分" width="90" align="right">
            <template #default="{ row }">{{ percent(row.score) }}</template>
          </el-table-column>
          <el-table-column label="延迟" width="100" align="right">
            <template #default="{ row }">{{ row.latency_ms }} ms</template>
          </el-table-column>
          <el-table-column label="模型" width="100">
            <template #default="{ row }">{{ row.model || '-' }}</template>
          </el-table-column>

          <template #empty>
            <el-empty :description="emptyText" :image-size="72" />
          </template>
        </el-table>

        <div class="table-pager">
          <el-pagination
            v-model:current-page="page"
            v-model:page-size="pageSize"
            :page-sizes="[10, 20, 50, 100]"
            :total="total"
            layout="total, sizes, prev, pager, next, jumper"
            background
            @current-change="onPageChange"
            @size-change="onSizeChange"
          />
        </div>
      </div>
    </template>

    <el-drawer
      v-model="detailVisible"
      :title="selected ? `${selected.id} · ${evalTypeLabel(selected.type)}` : '评测明细'"
      :size="drawerSize"
    >
      <div v-if="selected" class="detail-body">
        <p class="detail-question">{{ selected.question }}</p>
        <div class="detail-chips">
          <el-tag :type="selected.passed ? 'success' : 'danger'" effect="light">
            {{ selected.passed ? '通过' : '失败' }}
          </el-tag>
          <el-tag type="info" effect="plain">得分 {{ percent(selected.score) }}</el-tag>
          <el-tag type="info" effect="plain">{{ selected.latency_ms }} ms</el-tag>
          <el-tag v-if="selected.model" type="success" effect="plain">{{ selected.model }}</el-tag>
        </div>

        <el-alert
          v-if="selected.error"
          type="error"
          :closable="false"
          show-icon
          :title="selected.error"
          class="detail-alert"
        />

        <template v-if="selected.type === 'retrieval'">
          <div class="detail-section">
            <div class="section-title">命中 gold 文档</div>
            <div class="tag-row">
              <el-tag
                v-for="id in idList(selected.detail.hit_ids)"
                :key="id"
                type="success"
                effect="light"
              >
                #{{ id }}
              </el-tag>
              <span v-if="!idList(selected.detail.hit_ids).length" class="muted">无命中</span>
            </div>
          </div>
          <div class="detail-section">
            <div class="section-title">Gold 文档 ID</div>
            <div class="tag-row">
              <el-tag v-for="id in idList(selected.detail.gold_ids)" :key="id" effect="plain">
                #{{ id }}
              </el-tag>
            </div>
          </div>
          <div class="detail-section">
            <div class="section-title">Top-5 检索结果</div>
            <div class="tag-row">
              <el-tag v-for="id in idList(selected.detail.retrieved_ids)" :key="id" effect="plain">
                #{{ id }}
              </el-tag>
            </div>
          </div>
          <div class="detail-section">
            <div class="section-title">诊断 Recall</div>
            <span class="muted">关键词重叠召回：{{ percent(selected.detail.diagnostic_overlap_recall || 0) }}</span>
          </div>
        </template>

        <template v-else-if="selected.type === 'sql'">
          <div class="detail-section">
            <div class="section-title">生成 SQL</div>
            <pre class="sql-code">{{ selected.detail.generated_sql || '-' }}</pre>
          </div>
          <div class="detail-section">
            <div class="section-title">Gold SQL</div>
            <pre class="sql-code">{{ selected.detail.gold_sql || '-' }}</pre>
          </div>
          <div class="detail-section">
            <div class="section-title">生成结果</div>
            <ResultTable
              :columns="tableColumns(selected.detail.generated_rows)"
              :rows="tableRows(selected.detail.generated_rows)"
              :max-height="240"
            />
          </div>
          <div class="detail-section">
            <div class="section-title">Gold 结果</div>
            <ResultTable
              :columns="tableColumns(selected.detail.gold_rows)"
              :rows="tableRows(selected.detail.gold_rows)"
              :max-height="240"
            />
          </div>
        </template>

        <template v-else-if="selected.type === 'answer'">
          <div class="detail-section">
            <div class="section-title">
              回答
              <el-tag v-if="selected.detail.intent" size="small" effect="plain" class="inline-tag">
                {{ intentLabel(selected.detail.intent) }}
              </el-tag>
            </div>
            <div
              class="markdown-body answer-body"
              v-html="renderMarkdown(selected.detail.answer || '')"
            ></div>
          </div>
          <div class="detail-section">
            <div class="section-title">引用文档 ID</div>
            <div class="tag-row">
              <el-tag v-for="id in idList(selected.detail.citation_ids)" :key="id" effect="plain">
                #{{ id }}
              </el-tag>
            </div>
          </div>
          <div class="detail-section">
            <div class="section-title">缺失关键词</div>
            <div class="tag-row">
              <el-tag
                v-for="word in selected.detail.missing_keywords || []"
                :key="word"
                type="danger"
                effect="plain"
              >
                {{ word }}
              </el-tag>
              <span v-if="!(selected.detail.missing_keywords || []).length" class="muted">无缺失关键词</span>
            </div>
          </div>
        </template>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { Refresh, Search } from '@element-plus/icons-vue'

import EChart from '@/components/EChart.vue'
import ResultTable from '@/components/ResultTable.vue'
import { getEvalItems, getEvalReport } from '@/api/eval'
import { intentLabel } from '@/utils/format'
import { renderMarkdown } from '@/utils/markdown'
import type { EvalItem, EvalReport } from '@/types/api'

const loading = ref(false)
const errorMessage = ref('')
const report = ref<EvalReport | null>(null)

const typeFilter = ref('')
const resultFilter = ref('')
const keyword = ref('')
const page = ref(1)
const pageSize = ref(10)

const items = ref<EvalItem[]>([])
const total = ref(0)
const itemsLoading = ref(false)
const searchError = ref('')

const emptyText = computed(() => {
  if (searchError.value) return '数据加载失败，请点击上方重试'
  if (keyword.value.trim() || typeFilter.value || resultFilter.value) {
    return '没有符合条件的评测用例，试试更换关键词或筛选条件'
  }
  return '当前评测集暂无评测用例'
})

const detailVisible = ref(false)
const selected = ref<EvalItem | null>(null)

const viewportWidth = ref(window.innerWidth)
const drawerSize = computed(() => (viewportWidth.value < 720 ? '92%' : '660px'))

function handleResize(): void {
  viewportWidth.value = window.innerWidth
}

let keywordTimer: number | undefined
let itemsController: AbortController | null = null
let requestSeq = 0

const typeStats = computed(() => {
  const stats: Record<string, { passed: number; total: number }> = {
    retrieval: { passed: 0, total: 0 },
    sql: { passed: 0, total: 0 },
    answer: { passed: 0, total: 0 }
  }
  for (const item of report.value?.items || []) {
    const entry = stats[item.type]
    if (!entry) continue
    entry.total += 1
    if (item.passed) entry.passed += 1
  }
  return stats
})

const routeText = computed(() => {
  const routes = report.value?.meta.model_routes || {}
  return Object.entries(routes)
    .map(([key, value]) => `${key}: ${value}`)
    .join(' · ')
})

const latencyOption = computed(() => {
  const byType = report.value?.summary.latency_by_type_ms || {}
  const types = ['retrieval', 'sql', 'answer'].filter((type) => byType[type])
  if (types.length === 0) return null
  return {
    tooltip: { trigger: 'axis' },
    legend: { data: ['平均', 'P95'], top: 0 },
    grid: { left: 56, right: 24, top: 40, bottom: 30 },
    xAxis: { type: 'category', data: types.map((type) => evalTypeLabel(type)) },
    yAxis: { type: 'value', name: 'ms' },
    series: [
      {
        name: '平均',
        type: 'bar',
        barMaxWidth: 34,
        itemStyle: { color: '#93c5fd', borderRadius: [4, 4, 0, 0] },
        data: types.map((type) => byType[type].mean)
      },
      {
        name: 'P95',
        type: 'bar',
        barMaxWidth: 34,
        itemStyle: { color: '#2563eb', borderRadius: [4, 4, 0, 0] },
        data: types.map((type) => byType[type].p95)
      }
    ]
  }
})

onMounted(() => {
  window.addEventListener('resize', handleResize)
  load()
})

async function load(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    report.value = await getEvalReport()
    page.value = 1
    await loadItems()
  } catch (error) {
    report.value = null
    errorMessage.value = error instanceof Error ? error.message : '评测结果加载失败'
  } finally {
    loading.value = false
  }
}

function onKeywordInput(): void {
  clearKeywordTimer()
  keywordTimer = window.setTimeout(() => {
    keywordTimer = undefined
    applyFilters()
  }, 300)
}

function applyFilters(): void {
  clearKeywordTimer()
  page.value = 1
  loadItems()
}

function onPageChange(next: number): void {
  page.value = next
  loadItems()
}

function onSizeChange(): void {
  page.value = 1
  loadItems()
}

async function loadItems(): Promise<void> {
  itemsController?.abort()
  const controller = new AbortController()
  itemsController = controller
  const seq = ++requestSeq
  itemsLoading.value = true
  searchError.value = ''
  try {
    const data = await getEvalItems(
      {
        keyword: keyword.value,
        type: typeFilter.value,
        result: resultFilter.value,
        page: page.value,
        size: pageSize.value
      },
      controller.signal
    )
    if (seq !== requestSeq) return
    if (!data || !Array.isArray(data.items)) {
      throw new Error('评测用例接口返回格式异常')
    }
    items.value = data.items
    total.value = typeof data.total === 'number' ? data.total : data.items.length
  } catch (error) {
    if (seq !== requestSeq || controller.signal.aborted) return
    searchError.value = error instanceof Error ? error.message : '评测用例搜索失败'
  } finally {
    if (seq === requestSeq) itemsLoading.value = false
  }
}

function clearKeywordTimer(): void {
  if (keywordTimer) {
    window.clearTimeout(keywordTimer)
    keywordTimer = undefined
  }
}

onBeforeUnmount(() => {
  clearKeywordTimer()
  itemsController?.abort()
  window.removeEventListener('resize', handleResize)
})

function openDetail(row: EvalItem): void {
  selected.value = row
  detailVisible.value = true
}

function evalTypeLabel(type: string): string {
  const map: Record<string, string> = {
    retrieval: '文档检索',
    sql: 'SQL 查询',
    answer: '答案生成'
  }
  return map[type] || type
}

function percent(value: number): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '-'
  return `${(value * 100).toFixed(1)}%`
}

function idList(value: unknown): number[] {
  return Array.isArray(value) ? (value as number[]) : []
}

function tableColumns(rows: unknown): string[] {
  if (!Array.isArray(rows) || rows.length === 0) return []
  const first = rows[0]
  return first && typeof first === 'object' ? Object.keys(first) : []
}

function tableRows(rows: unknown): Record<string, unknown>[] {
  return Array.isArray(rows) ? (rows as Record<string, unknown>[]) : []
}
</script>

<style scoped>
.eval-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
  height: 100%;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  overscroll-behavior: contain;
}

/* 固定高度滚动容器内的子项禁止压缩，保证内容自然高度并可滚动查看 */
.eval-page > * {
  flex: none;
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

.empty-panel {
  padding: 20px;
  text-align: center;
}

.empty-hint {
  margin: 0;
  font-size: 12px;
}

.empty-hint code {
  padding: 2px 6px;
  border-radius: 4px;
  background: #f1f5f9;
  font-family: Consolas, 'Courier New', monospace;
}

.meta-bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px 18px;
  padding: 12px 16px;
  font-size: 12.5px;
  color: #475569;
}

.meta-bar b {
  margin-right: 4px;
  color: var(--muted);
  font-weight: 600;
}

.meta-routes {
  min-width: 0;
}

.meta-sha {
  cursor: help;
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
  font-size: 26px;
  font-weight: 700;
  line-height: 1.2;
  color: #15803d;
}

.stat-value.latency {
  color: #1d4ed8;
}

.stat-value small {
  margin-left: 2px;
  font-size: 13px;
  font-weight: 500;
  color: var(--muted);
}

.stat-sub {
  font-size: 12px;
}

.chart-panel {
  padding: 14px 16px;
}

.table-panel {
  flex: none;
  display: flex;
  flex-direction: column;
  padding: 12px 12px 0;
}

.table-toolbar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  padding-bottom: 10px;
}

.filter-select {
  width: 140px;
  flex: 0 0 auto;
}

.search-input {
  width: 260px;
  min-width: 160px;
  flex: 1 1 200px;
}

.search-alert {
  margin-bottom: 10px;
}

.toolbar-count {
  margin-left: auto;
  font-size: 12px;
}

.eval-table {
  flex: none;
  min-height: 240px;
}

.eval-table :deep(.el-table__row) {
  cursor: pointer;
}

.table-pager {
  display: flex;
  justify-content: flex-end;
  padding: 10px 4px;
}

.table-pager :deep(.el-pagination) {
  flex-wrap: wrap;
  row-gap: 8px;
  justify-content: flex-end;
}

.detail-question {
  margin: 0 0 10px;
  font-size: 15px;
  font-weight: 600;
  line-height: 1.6;
}

.detail-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 14px;
}

.detail-alert {
  margin-bottom: 12px;
}

.detail-section {
  margin-bottom: 16px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--muted);
}

.inline-tag {
  font-weight: 400;
}

.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.sql-code {
  margin: 0;
  padding: 12px 14px;
  overflow: auto;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: #f8fafc;
  font-family: Consolas, 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-all;
  color: #334155;
}

.answer-body {
  padding: 12px 14px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: #fbfcfe;
}

@media (max-width: 1000px) {
  .stat-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .search-input {
    width: 100%;
  }

  .toolbar-count {
    margin-left: 0;
  }
}

@media (max-width: 720px) {
  .table-toolbar {
    align-items: stretch;
  }

  .filter-select,
  .search-input {
    width: 100%;
    flex: 1 1 100%;
  }

  .table-pager {
    justify-content: center;
    padding: 10px 0;
  }

  .table-pager :deep(.el-pagination) {
    justify-content: center;
  }
}

@media (max-width: 560px) {
  .stat-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
