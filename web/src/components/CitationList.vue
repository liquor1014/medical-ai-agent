<template>
  <div v-if="citations.length" class="citation-list">
    <div class="citation-head">
      <el-icon><Link /></el-icon>
      <span>引用来源（{{ citations.length }}）</span>
    </div>

    <div class="citation-items">
      <div
        v-for="(item, index) in citations"
        :key="index"
        class="citation-card"
        :class="{ clickable: item.doc_id || item.report_id }"
        @click="onClick(item)"
      >
        <template v-if="item.type === 'report' || item.report_id">
          <div class="citation-title">
            <el-tag size="small" type="success" effect="plain">报表</el-tag>
            <span>{{ item.title || `报表 #${item.report_id}` }}</span>
          </div>
          <div class="citation-meta muted">共 {{ item.row_count ?? 0 }} 行数据</div>
        </template>

        <template v-else>
          <div class="citation-title">
            <span class="citation-index">片段 {{ index + 1 }}</span>
            <span class="citation-meta">
              文档 #{{ item.doc_id }} · 第 {{ item.page_no ?? '-' }} 页
              <template v-if="item.section"> · {{ item.section }}</template>
            </span>
          </div>
          <p class="citation-content">{{ item.content }}</p>
        </template>

        <div v-if="item.doc_id || item.report_id" class="citation-open">
          查看来源
          <el-icon><ArrowRight /></el-icon>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Citation } from '@/types/api'

const props = defineProps<{
  citations: Citation[]
}>()

const emit = defineEmits<{
  (event: 'open-document', docId: number, pageNo?: number): void
  (event: 'open-report', reportId: number): void
}>()

function onClick(item: Citation): void {
  if (item.report_id) {
    emit('open-report', item.report_id)
    return
  }
  if (item.doc_id) {
    emit('open-document', item.doc_id, item.page_no ?? undefined)
  }
}

void props
</script>

<style scoped>
.citation-list {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed var(--border);
}

.citation-head {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--muted);
}

.citation-items {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 10px;
}

.citation-card {
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: #fbfcfe;
  font-size: 13px;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.citation-card.clickable {
  cursor: pointer;
}

.citation-card.clickable:hover {
  border-color: #93c5fd;
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.12);
}

.citation-title {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  font-weight: 600;
}

.citation-index {
  color: var(--brand);
}

.citation-meta {
  font-weight: 400;
  color: var(--muted);
  font-size: 12px;
}

.citation-content {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
  margin: 6px 0 0;
  color: #475569;
  line-height: 1.6;
}

.citation-open {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 2px;
  margin-top: 6px;
  font-size: 12px;
  color: var(--brand);
}
</style>
