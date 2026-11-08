<template>
  <div class="reports-page page-block">
    <div class="page-head">
      <div>
        <h2>报表中心</h2>
        <p class="muted">
          NL2SQL 生成的三类固定报表：库存周转、供应商履约、科室消耗排名；支持 SQL 预览、图表与 CSV 导出。
        </p>
      </div>
      <el-button :icon="Refresh" :loading="loading" @click="loadList">刷新</el-button>
    </div>

    <div class="reports-layout">
      <section class="report-list panel">
        <div class="list-head">
          <span>报表记录</span>
          <span class="muted">{{ reports.length }}</span>
        </div>
        <el-scrollbar class="list-scroll">
          <div
            v-for="report in reports"
            :key="report.id"
            class="report-item"
            :class="{ active: current?.id === report.id }"
            @click="selectReport(report.id)"
          >
            <div class="report-item-head">
              <span class="report-question">{{ report.question }}</span>
              <el-tag size="small" :type="reportStatusMeta(report.status).type" effect="plain">
                {{ reportStatusMeta(report.status).label }}
              </el-tag>
            </div>
            <div class="report-item-meta muted">
              <span>{{ reportChartLabel(report.chartType) }}</span>
              <span>{{ report.rowCount }} 行</span>
              <span>{{ formatDateTime(report.createdAt) }}</span>
            </div>
          </div>

          <el-empty
            v-if="!reports.length && !loading"
            description="还没有报表。在智能问答中提问“生成库存周转报表”即可创建"
            :image-size="72"
          />
        </el-scrollbar>
      </section>

      <section class="report-detail panel">
        <template v-if="current">
          <header class="detail-head">
            <div class="detail-title">
              <h3>{{ current.question }}</h3>
              <p class="muted">
                报表 #{{ current.id }} · {{ formatDateTime(current.createdAt) }} ·
                {{ reportChartLabel(current.chartType) }}
              </p>
            </div>
            <el-button :icon="Download" :loading="exporting" @click="onExport">导出 CSV</el-button>
          </header>

          <el-tabs v-model="tab" class="detail-tabs">
            <el-tab-pane label="图表" name="chart">
              <EChart v-if="chartOption" :option="chartOption" height="360px" />
              <el-empty
                v-else
                description="该报表没有可绘制的数值列，请查看数据表"
                :image-size="72"
              />
            </el-tab-pane>

            <el-tab-pane label="数据表" name="table">
              <ResultTable
                :columns="current.columns"
                :rows="current.rows"
                :row-count="current.rows.length"
                :max-height="420"
              />
            </el-tab-pane>

            <el-tab-pane label="SQL 预览" name="sql">
              <div class="sql-actions">
                <span class="muted">只读 SQL，已注入租户过滤与 LIMIT</span>
                <el-button size="small" :icon="CopyDocument" @click="copySql">复制 SQL</el-button>
              </div>
              <pre class="sql-code">{{ current.sql || '暂无 SQL' }}</pre>
            </el-tab-pane>
          </el-tabs>
        </template>

        <el-empty v-else description="从左侧选择一张报表查看详情" />
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { CopyDocument, Download, Refresh } from '@element-plus/icons-vue'

import EChart from '@/components/EChart.vue'
import ResultTable from '@/components/ResultTable.vue'
import { exportReport, getReport, listReports } from '@/api/reports'
import { buildChartOption } from '@/utils/chart'
import { formatDateTime, reportChartLabel, reportStatusMeta } from '@/utils/format'
import type { ReportDetail, ReportSummary } from '@/types/api'

const route = useRoute()
const router = useRouter()

const reports = ref<ReportSummary[]>([])
const current = ref<ReportDetail | null>(null)
const loading = ref(false)
const exporting = ref(false)
const tab = ref<'chart' | 'table' | 'sql'>('chart')

const chartOption = computed(() => {
  if (!current.value) return null
  return buildChartOption(
    current.value.columns,
    current.value.rows,
    current.value.chartType,
    current.value.question
  )
})

onMounted(async () => {
  await loadList()
  await openFromQuery()
})

watch(() => route.query.reportId, openFromQuery)

async function loadList(): Promise<void> {
  loading.value = true
  try {
    reports.value = await listReports()
    if (current.value && !reports.value.some((item) => item.id === current.value?.id)) {
      current.value = null
    }
    const queryId = Number(route.query.reportId)
    if (!current.value && !Number.isNaN(queryId) && reports.value.some((item) => item.id === queryId)) {
      await loadDetail(queryId)
    }
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '报表列表加载失败')
  } finally {
    loading.value = false
  }
}

async function openFromQuery(): Promise<void> {
  const raw = route.query.reportId
  if (!raw) {
    if (!current.value && reports.value.length > 0) {
      await loadDetail(reports.value[0].id)
    }
    return
  }
  const id = Number(raw)
  if (Number.isNaN(id)) {
    await router.replace({ path: '/reports' })
    return
  }
  await loadDetail(id)
}

async function selectReport(id: number): Promise<void> {
  if (id === current.value?.id) return
  await loadDetail(id)
  await router.replace({ path: '/reports', query: { reportId: String(id) } })
}

async function loadDetail(id: number): Promise<void> {
  try {
    current.value = await getReport(id)
    tab.value = chartOption.value ? 'chart' : 'table'
  } catch (error) {
    current.value = null
    ElMessage.error(error instanceof Error ? error.message : '报表详情加载失败')
  }
}

async function onExport(): Promise<void> {
  if (!current.value) return
  exporting.value = true
  try {
    await exportReport(current.value.id)
    ElMessage.success('CSV 已开始下载')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '导出失败')
  } finally {
    exporting.value = false
  }
}

async function copySql(): Promise<void> {
  const sql = current.value?.sql
  if (!sql) return
  try {
    await navigator.clipboard.writeText(sql)
    ElMessage.success('SQL 已复制')
  } catch {
    ElMessage.warning('复制失败，请手动选择 SQL 文本')
  }
}
</script>

<style scoped>
.reports-page {
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

.reports-layout {
  flex: 1;
  display: grid;
  grid-template-columns: 340px minmax(0, 1fr);
  gap: 14px;
  min-height: 0;
}

.report-list {
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

.list-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border);
  font-size: 14px;
  font-weight: 600;
}

.list-scroll {
  flex: 1;
  min-height: 0;
  padding: 8px;
}

.report-item {
  padding: 12px;
  border: 1px solid transparent;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease;
}

.report-item:hover {
  background: #f8fafc;
}

.report-item.active {
  border-color: #bfdbfe;
  background: #eef4ff;
}

.report-item-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}

.report-question {
  font-size: 13px;
  font-weight: 600;
  line-height: 1.5;
  color: var(--text);
}

.report-item-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 8px;
  font-size: 12px;
}

.report-detail {
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding: 0 18px 18px;
  overflow: hidden;
}

.detail-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 0 10px;
  border-bottom: 1px solid var(--border);
}

.detail-title h3 {
  margin: 0 0 4px;
  font-size: 16px;
}

.detail-title p {
  margin: 0;
}

.detail-tabs {
  flex: 1;
  min-height: 0;
  margin-top: 4px;
}

.detail-tabs :deep(.el-tabs__content) {
  height: calc(100% - 46px);
  overflow: auto;
  padding-top: 12px;
}

.sql-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 12px;
}

.sql-code {
  margin: 0;
  padding: 14px 16px;
  overflow: auto;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: #f8fafc;
  font-family: Consolas, 'Courier New', monospace;
  font-size: 12.5px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-all;
  color: #334155;
}

@media (max-width: 1000px) {
  .reports-layout {
    grid-template-columns: 1fr;
    grid-template-rows: auto minmax(0, 1fr);
  }

  .report-list {
    max-height: 220px;
  }
}
</style>
