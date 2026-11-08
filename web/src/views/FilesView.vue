<template>
  <div class="files-page page-block">
    <div class="page-head">
      <div>
        <h2>文件库</h2>
        <p class="muted">
          上传院内制度与耗材文档，系统自动解析、切片并建立检索索引；问答时按页码给出引用。
        </p>
      </div>
      <el-button type="primary" :icon="Upload" @click="uploadVisible = true">上传文档</el-button>
    </div>

    <div class="toolbar panel">
      <el-input
        v-model="keyword"
        class="search-input"
        placeholder="按文件名搜索"
        clearable
        :prefix-icon="Search"
      />
      <el-select v-model="statusFilter" class="filter-select">
        <el-option label="全部状态" value="all" />
        <el-option label="待解析" value="pending" />
        <el-option label="解析中" value="parsing" />
        <el-option label="已完成" value="completed" />
        <el-option label="解析失败" value="failed" />
      </el-select>
      <el-select v-model="typeFilter" class="filter-select">
        <el-option label="全部类型" value="all" />
        <el-option label="PDF" value="pdf" />
        <el-option label="Word" value="docx" />
        <el-option label="文本" value="txt" />
        <el-option label="Markdown" value="md" />
        <el-option label="图片" value="image" />
      </el-select>
      <el-button :icon="Refresh" :loading="loading" @click="load()">刷新</el-button>
      <div class="toolbar-status muted">
        <el-icon v-if="polling" class="is-loading"><Loading /></el-icon>
        <span v-if="polling">解析进行中，自动刷新…</span>
        <span v-else>共 {{ filteredDocuments.length }} 份文档</span>
      </div>
    </div>

    <div class="table-panel panel">
      <el-table
        v-loading="loading"
        :data="pagedDocuments"
        row-key="id"
        class="doc-table"
        @row-click="openDetail"
      >
        <el-table-column label="文件名" min-width="260">
          <template #default="{ row }">
            <div class="file-cell">
              <el-icon class="file-icon"><Document /></el-icon>
              <div class="file-meta">
                <span class="file-name">{{ row.fileName }}</span>
                <span class="file-sub">文档 #{{ row.id }}</span>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="90">
          <template #default="{ row }">{{ docTypeLabel(row.docType) }}</template>
        </el-table-column>
        <el-table-column label="解析状态" width="110">
          <template #default="{ row }">
            <el-tag :type="documentStatusMeta(row.status).type" size="small" effect="light">
              {{ documentStatusMeta(row.status).label }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="页数" width="80" align="right">
          <template #default="{ row }">{{ row.pageCount || '-' }}</template>
        </el-table-column>
        <el-table-column label="切片数" width="90" align="right">
          <template #default="{ row }">{{ row.chunkCount || '-' }}</template>
        </el-table-column>
        <el-table-column label="上传时间" width="160">
          <template #default="{ row }">{{ formatDateTime(row.createdAt) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="130" align="center">
          <template #default="{ row }">
            <div class="row-actions" @click.stop>
              <el-button link type="primary" size="small" @click="openDetail(row)">详情</el-button>
              <el-popconfirm
                title="删除后切片与索引一并移除，确定删除？"
                confirm-button-text="删除"
                cancel-button-text="取消"
                width="240"
                @confirm="removeDocument(row)"
              >
                <template #reference>
                  <el-button link type="danger" size="small">删除</el-button>
                </template>
              </el-popconfirm>
            </div>
          </template>
        </el-table-column>

        <template #empty>
          <el-empty description="还没有文档，先上传一份医疗 PDF 开始构建知识库">
            <el-button type="primary" @click="uploadVisible = true">上传文档</el-button>
          </el-empty>
        </template>
      </el-table>

      <div class="table-pager">
        <el-pagination
          v-model:current-page="page"
          :page-size="pageSize"
          :total="filteredDocuments.length"
          layout="total, prev, pager, next"
          background
          hide-on-single-page
        />
      </div>
    </div>

    <el-dialog v-model="uploadVisible" title="上传文档" width="560px">
      <el-upload
        drag
        multiple
        :http-request="uploadOne"
        :on-success="onUploadSuccess"
        :on-error="onUploadError"
        accept=".pdf,.docx,.doc,.txt,.md,.png,.jpg,.jpeg,.bmp,.tif,.tiff,.webp"
      >
        <el-icon class="upload-icon"><UploadFilled /></el-icon>
        <div class="upload-text">将文件拖到此处，或<em>点击选择</em></div>
        <template #tip>
          <div class="upload-tip muted">
            支持 PDF / Word / 文本 / 图片，单次可多选。上传后异步解析，可关闭窗口在列表中查看进度。
          </div>
        </template>
      </el-upload>
    </el-dialog>

    <el-drawer v-model="detailVisible" title="文档详情" size="480px">
      <div v-if="detailDoc" class="detail-body">
        <div class="detail-head">
          <div class="detail-file">
            <el-icon><Document /></el-icon>
            <div>
              <h3>{{ detailDoc.fileName }}</h3>
              <p class="muted">文档 #{{ detailDoc.id }} · {{ docTypeLabel(detailDoc.docType) }}</p>
            </div>
          </div>
          <el-tag :type="documentStatusMeta(detailDoc.status).type" effect="light">
            {{ documentStatusMeta(detailDoc.status).label }}
          </el-tag>
        </div>

        <el-alert
          v-if="citedPage"
          type="info"
          :closable="false"
          show-icon
          :title="`来自问答引用：第 ${citedPage} 页`"
          class="detail-alert"
        />

        <el-alert
          v-if="detailDoc.status === 'failed'"
          type="error"
          :closable="false"
          show-icon
          title="解析失败"
          description="请确认 AI 服务可用后删除并重新上传该文档。"
          class="detail-alert"
        />
        <el-alert
          v-else-if="detailDoc.status === 'pending' || detailDoc.status === 'parsing'"
          type="warning"
          :closable="false"
          show-icon
          title="解析进行中"
          description="列表会自动刷新，完成后即可在智能问答中引用该文档。"
          class="detail-alert"
        />
        <el-alert
          v-else-if="detailDoc.status === 'completed'"
          type="success"
          :closable="false"
          show-icon
          :title="`解析完成，共 ${detailDoc.pageCount} 页 / ${detailDoc.chunkCount} 个切片`"
          description="可在「智能问答」中提问，回答会带页码引用。"
          class="detail-alert"
        />

        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="文档 ID">{{ detailDoc.id }}</el-descriptions-item>
          <el-descriptions-item label="所属租户">{{ detailDoc.tenantId }}</el-descriptions-item>
          <el-descriptions-item label="文档类型">{{ docTypeLabel(detailDoc.docType) }}</el-descriptions-item>
          <el-descriptions-item label="页数">{{ detailDoc.pageCount || 0 }}</el-descriptions-item>
          <el-descriptions-item label="切片数">{{ detailDoc.chunkCount || 0 }}</el-descriptions-item>
          <el-descriptions-item label="上传时间">{{ formatDateTime(detailDoc.createdAt) }}</el-descriptions-item>
          <el-descriptions-item label="存储路径">
            <span class="object-key">{{ detailDoc.objectKey }}</span>
          </el-descriptions-item>
        </el-descriptions>

        <div class="detail-actions">
          <el-button :icon="ChatDotRound" type="primary" plain @click="gotoChat">就这份文档提问</el-button>
          <el-popconfirm
            title="删除后切片与索引一并移除，确定删除？"
            confirm-button-text="删除"
            cancel-button-text="取消"
            width="240"
            @confirm="removeDocument(detailDoc)"
          >
            <template #reference>
              <el-button type="danger" plain :icon="Delete">删除文档</el-button>
            </template>
          </el-popconfirm>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ChatDotRound, Delete, Document, Loading, Refresh, Search, Upload, UploadFilled } from '@element-plus/icons-vue'
import type { UploadRequestOptions } from 'element-plus'

import { deleteDocument, getDocument, listDocuments, uploadDocument } from '@/api/files'
import {
  documentStatusMeta,
  docTypeLabel,
  formatDateTime
} from '@/utils/format'
import type { DocumentItem } from '@/types/api'

const route = useRoute()
const router = useRouter()

const documents = ref<DocumentItem[]>([])
const loading = ref(false)
const keyword = ref('')
const statusFilter = ref('all')
const typeFilter = ref('all')
const page = ref(1)
const pageSize = 10

const uploadVisible = ref(false)
const detailVisible = ref(false)
const detailDoc = ref<DocumentItem | null>(null)
const citedPage = ref<number | null>(null)

let pollTimer: number | undefined
let fetching = false

const filteredDocuments = computed(() => {
  const key = keyword.value.trim().toLowerCase()
  return documents.value.filter((doc) => {
    if (key && !doc.fileName.toLowerCase().includes(key)) return false
    if (statusFilter.value !== 'all' && doc.status !== statusFilter.value) return false
    if (typeFilter.value !== 'all' && doc.docType !== typeFilter.value) return false
    return true
  })
})

const pagedDocuments = computed(() => {
  const start = (page.value - 1) * pageSize
  return filteredDocuments.value.slice(start, start + pageSize)
})

const polling = computed(() =>
  documents.value.some((doc) => doc.status === 'pending' || doc.status === 'parsing')
)

watch([keyword, statusFilter, typeFilter], () => {
  page.value = 1
})

watch(
  () => filteredDocuments.value.length,
  (total) => {
    const maxPage = Math.max(1, Math.ceil(total / pageSize))
    if (page.value > maxPage) page.value = maxPage
  }
)

onMounted(async () => {
  await load()
  await openFromQuery()
})

onBeforeUnmount(() => {
  stopPolling()
})

async function load(silent = false): Promise<void> {
  if (fetching) return
  fetching = true
  if (!silent) loading.value = true
  try {
    documents.value = await listDocuments()
  } catch (error) {
    if (!silent) {
      ElMessage.error(error instanceof Error ? error.message : '文档列表加载失败')
    }
  } finally {
    loading.value = false
    fetching = false
    syncPolling()
  }
}

function syncPolling(): void {
  if (polling.value) {
    if (!pollTimer) {
      pollTimer = window.setInterval(() => load(true), 3000)
    }
  } else {
    stopPolling()
  }
}

function stopPolling(): void {
  if (pollTimer) {
    window.clearInterval(pollTimer)
    pollTimer = undefined
  }
}

async function uploadOne(options: UploadRequestOptions): Promise<unknown> {
  const file = options.file as File
  return uploadDocument(file)
}

function onUploadSuccess(): void {
  ElMessage.success('已上传，正在解析文档')
  load()
}

function onUploadError(error: Error): void {
  ElMessage.error(error?.message || '上传失败，请重试')
}

async function openDetail(row: DocumentItem): Promise<void> {
  citedPage.value = null
  try {
    detailDoc.value = await getDocument(row.id)
    detailVisible.value = true
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '文档详情加载失败')
  }
}

async function removeDocument(row: DocumentItem): Promise<void> {
  try {
    await deleteDocument(row.id)
    ElMessage.success('文档已删除')
    if (detailDoc.value?.id === row.id) {
      detailVisible.value = false
      detailDoc.value = null
    }
    await load()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '删除失败')
  }
}

async function openFromQuery(): Promise<void> {
  const rawDocId = route.query.docId
  if (!rawDocId) return
  const docId = Number(rawDocId)
  if (Number.isNaN(docId)) return
  const pageNo = Number(route.query.page)
  citedPage.value = Number.isNaN(pageNo) || !route.query.page ? null : pageNo
  try {
    detailDoc.value = await getDocument(docId)
    detailVisible.value = true
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '引用文档不存在或无权访问')
    router.replace({ path: '/files' })
  }
}

watch(() => route.query.docId, openFromQuery)

function gotoChat(): void {
  detailVisible.value = false
  router.push('/chat')
}
</script>

<style scoped>
.files-page {
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

.toolbar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  padding: 12px 14px;
}

.search-input {
  width: 260px;
}

.filter-select {
  width: 140px;
}

.toolbar-status {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-left: auto;
}

.table-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding: 6px 6px 0;
}

.doc-table {
  flex: 1;
}

.doc-table :deep(.el-table__row) {
  cursor: pointer;
}

.file-cell {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.file-icon {
  flex: none;
  color: var(--brand);
  font-size: 18px;
}

.file-meta {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.file-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 500;
}

.file-sub {
  font-size: 12px;
  color: var(--muted);
}

.row-actions {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}

.table-pager {
  display: flex;
  justify-content: flex-end;
  padding: 10px 6px;
}

.upload-icon {
  font-size: 40px;
  color: #94a3b8;
  margin-top: 8px;
}

.upload-text {
  font-size: 13px;
  color: var(--muted);
}

.upload-text em {
  color: var(--brand);
  font-style: normal;
}

.upload-tip {
  margin-top: 8px;
  font-size: 12px;
  line-height: 1.6;
}

.detail-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.detail-file {
  display: flex;
  gap: 10px;
}

.detail-file .el-icon {
  margin-top: 4px;
  font-size: 22px;
  color: var(--brand);
}

.detail-file h3 {
  margin: 0 0 4px;
  font-size: 16px;
  word-break: break-all;
}

.detail-file p {
  margin: 0;
}

.detail-alert {
  margin-bottom: 12px;
}

.object-key {
  word-break: break-all;
  font-family: Consolas, 'Courier New', monospace;
  font-size: 12px;
  color: var(--muted);
}

.detail-actions {
  display: flex;
  gap: 10px;
  margin-top: 18px;
}

@media (max-width: 720px) {
  .search-input,
  .filter-select {
    width: 100%;
  }

  .toolbar-status {
    margin-left: 0;
  }
}
</style>
