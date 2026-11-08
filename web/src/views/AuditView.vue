<template>
  <div class="audit-page page-block">
    <div class="page-head">
      <div>
        <h2>审计日志</h2>
        <p class="muted">
          记录 AI 每次 NL2SQL 的只读 SQL 执行结果（success / rejected），按租户隔离，用于排查拦截原因与追溯操作。
        </p>
      </div>
      <el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button>
    </div>

    <div class="stat-grid">
      <div class="stat-card panel">
        <span class="stat-label">总记录</span>
        <span class="stat-value">{{ totalCount }}</span>
        <span class="stat-sub muted">当前租户累计</span>
      </div>
      <div class="stat-card panel">
        <span class="stat-label">成功执行</span>
        <span class="stat-value success">{{ counts.success || 0 }}</span>
        <span class="stat-sub muted">通过 SQL Guard 并返回结果</span>
      </div>
      <div class="stat-card panel">
        <span class="stat-label">已拦截</span>
        <span class="stat-value danger">{{ counts.rejected || 0 }}</span>
        <span class="stat-sub muted">写操作 / 越权 / 非白名单</span>
      </div>
      <div class="stat-card panel">
        <span class="stat-label">近 24 小时</span>
        <span class="stat-value">{{ last24h }}</span>
        <span class="stat-sub muted">最近一天审计量</span>
      </div>
    </div>

    <div class="toolbar panel">
      <el-radio-group v-model="resultFilter" @change="applyFilters">
        <el-radio-button value="">全部</el-radio-button>
        <el-radio-button value="success">成功</el-radio-button>
        <el-radio-button value="rejected">已拦截</el-radio-button>
      </el-radio-group>

      <el-select v-model="actionFilter" class="action-select" @change="applyFilters">
        <el-option label="全部动作" value="" />
        <el-option
          v-for="action in pageData.actions"
          :key="action"
          :label="actionLabel(action)"
          :value="action"
        />
      </el-select>

      <span class="toolbar-hint muted">仅展示当前租户审计记录</span>
    </div>

    <div class="table-panel panel">
      <el-table v-loading="loading" :data="pageData.items" class="audit-table">
        <el-table-column label="时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.createdAt) }}</template>
        </el-table-column>
        <el-table-column label="动作" width="130">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ actionLabel(row.action) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="结果" width="110">
          <template #default="{ row }">
            <el-tag size="small" :type="resultMeta(row.result).type" effect="light">
              {{ resultMeta(row.result).label }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="SQL Hash" min-width="280">
          <template #default="{ row }">
            <div v-if="row.sqlHash" class="hash-cell">
              <el-tooltip :content="row.sqlHash" placement="top">
                <span class="hash-text">{{ row.sqlHash.slice(0, 24) }}…</span>
              </el-tooltip>
              <el-button
                link
                type="primary"
                size="small"
                :icon="CopyDocument"
                @click="copyHash(row.sqlHash)"
              >
                复制
              </el-button>
            </div>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作人" width="110">
          <template #default="{ row }">
            {{ row.userId === 0 ? '智能体' : `用户 #${row.userId}` }}
          </template>
        </el-table-column>
        <el-table-column label="租户" width="140" prop="tenantId" show-overflow-tooltip />

        <template #empty>
          <el-empty
            description="当前筛选条件下暂无审计记录"
            :image-size="72"
          >
            <el-button v-if="resultFilter" @click="resetFilters">清除筛选</el-button>
          </el-empty>
        </template>
      </el-table>

      <div class="table-pager">
        <el-pagination
          v-model:current-page="page"
          :page-size="size"
          :total="pageData.total"
          layout="total, prev, pager, next"
          background
          hide-on-single-page
          @current-change="load"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { CopyDocument, Refresh } from '@element-plus/icons-vue'

import { listAuditLogs } from '@/api/audit'
import { formatDateTime } from '@/utils/format'
import type { AuditPage } from '@/types/api'

const loading = ref(false)
const page = ref(1)
const size = 20
const resultFilter = ref('')
const actionFilter = ref('')

const pageData = ref<AuditPage>({
  items: [],
  total: 0,
  page: 1,
  size,
  counts: {},
  last24h: 0,
  actions: []
})

const counts = computed(() => pageData.value.counts)
const totalCount = computed(() =>
  Object.values(counts.value).reduce((sum, value) => sum + value, 0)
)
const last24h = computed(() => pageData.value.last24h)

onMounted(load)

async function load(): Promise<void> {
  loading.value = true
  try {
    const data = await listAuditLogs({
      page: page.value,
      size,
      action: actionFilter.value,
      result: resultFilter.value
    })
    pageData.value = data
    page.value = data.page
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '审计日志加载失败')
  } finally {
    loading.value = false
  }
}

function applyFilters(): void {
  page.value = 1
  load()
}

function resetFilters(): void {
  resultFilter.value = ''
  actionFilter.value = ''
  applyFilters()
}

function actionLabel(action: string): string {
  const map: Record<string, string> = {
    nl2sql: 'NL2SQL 查询',
    report_export: '报表导出',
    file_delete: '文档删除'
  }
  return map[action] || action
}

function resultMeta(result: string | null): { label: string; type: 'success' | 'danger' | 'info' } {
  switch (result) {
    case 'success':
      return { label: '成功', type: 'success' }
    case 'rejected':
      return { label: '已拦截', type: 'danger' }
    case 'failed':
      return { label: '执行失败', type: 'danger' }
    default:
      return { label: result || '未知', type: 'info' }
  }
}

async function copyHash(hash: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(hash)
    ElMessage.success('SQL Hash 已复制')
  } catch {
    ElMessage.warning('复制失败，请手动选择文本')
  }
}
</script>

<style scoped>
.audit-page {
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
  color: var(--text);
}

.stat-value.success {
  color: #15803d;
}

.stat-value.danger {
  color: #b91c1c;
}

.stat-sub {
  font-size: 12px;
}

.toolbar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  padding: 12px 14px;
}

.action-select {
  width: 160px;
}

.toolbar-hint {
  margin-left: auto;
  font-size: 12px;
}

.table-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding: 6px 6px 0;
}

.audit-table {
  flex: 1;
}

.hash-cell {
  display: flex;
  align-items: center;
  gap: 6px;
}

.hash-text {
  font-family: Consolas, 'Courier New', monospace;
  font-size: 12px;
  color: #475569;
}

.table-pager {
  display: flex;
  justify-content: flex-end;
  padding: 10px 6px;
}

@media (max-width: 1000px) {
  .stat-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .toolbar-hint {
    margin-left: 0;
  }
}
</style>
