<template>
  <div class="chat-page">
    <aside v-show="historyVisible" class="history-panel panel">
      <div class="history-head">
        <span class="history-title-label">历史对话</span>
        <el-button link size="small" :icon="Plus" @click="newSession">新会话</el-button>
      </div>

      <el-input
        v-model="sessionKeyword"
        class="history-search"
        size="small"
        clearable
        placeholder="搜索关键词"
        :prefix-icon="Search"
        @keyup.enter="loadSessions"
        @clear="loadSessions"
      />
      <el-date-picker
        v-model="dateRange"
        type="daterange"
        size="small"
        value-format="YYYY-MM-DD"
        start-placeholder="开始日期"
        end-placeholder="结束日期"
        unlink-panels
        teleported
        class="history-date"
        popper-class="history-date-popper"
        style="width: 100%; height: 30px"
        @change="loadSessions"
      />

      <div class="history-list">
        <div v-if="sessionsLoading" class="history-empty">加载中...</div>
        <div v-else-if="sessionsError" class="history-empty history-error">{{ sessionsError }}</div>
        <div v-else-if="sessions.length === 0" class="history-empty">暂无历史对话</div>
        <template v-else>
          <button
            v-for="item in sessions"
            :key="item.session_id"
            class="history-item"
            :class="{ active: item.session_id === activeSessionId }"
            @click="selectSession(item)"
          >
            <span class="history-item-title">{{ item.title }}</span>
            <span class="history-item-preview">{{ item.preview || '—' }}</span>
            <span class="history-item-meta">
              <span>{{ item.last_active_at ? formatDateTime(item.last_active_at) : '' }}</span>
              <span>{{ item.message_count }} 条</span>
            </span>
          </button>
        </template>
      </div>
    </aside>

    <div class="chat-shell panel">
      <header class="chat-header">
        <div>
          <h2>智能问答</h2>
          <p class="muted">
            文档问答可按页码追溯引用；数据查询与报表由 NL2SQL 生成，仅执行只读 SQL。
          </p>
        </div>
        <div class="chat-header-actions">
          <el-tag v-if="lastModel" size="small" type="success" effect="plain">
            {{ lastModel.provider }} · {{ lastModel.model }}
          </el-tag>
          <el-button size="small" :icon="Clock" @click="historyVisible = !historyVisible">
            {{ historyVisible ? '收起历史' : '历史对话' }}
          </el-button>
          <el-button size="small" :icon="Plus" @click="newSession">新会话</el-button>
        </div>
      </header>

      <div ref="scrollRef" class="chat-scroll" :class="{ 'is-loading-history': historyLoading }">
        <div v-if="historyLoading" class="history-loading-mask">正在加载历史消息...</div>
        <div v-if="messages.length === 0" class="chat-welcome">
          <div class="welcome-icon">
            <el-icon><ChatDotRound /></el-icon>
          </div>
          <h3>从一份文档或一张报表开始</h3>
          <p class="muted">点击示例问题填入输入框，或直接提问。</p>
          <div class="suggestions">
            <button
              v-for="question in suggestions"
              :key="question"
              class="suggestion"
              @click="useSuggestion(question)"
            >
              {{ question }}
            </button>
          </div>
        </div>

        <div
          v-for="msg in messages"
          :key="msg.id"
          class="message"
          :class="msg.role"
        >
          <div class="avatar">{{ msg.role === 'user' ? '我' : 'AI' }}</div>
          <div class="message-body">
            <div class="message-meta">
              <span class="sender">{{ msg.role === 'user' ? '我' : '助手' }}</span>
              <el-tag v-if="msg.intent" size="small" effect="plain">
                {{ intentLabel(msg.intent) }}
              </el-tag>
              <el-tag
                v-if="msg.retrievalCount"
                size="small"
                type="info"
                effect="plain"
              >
                检索 {{ msg.retrievalCount }} 片段
              </el-tag>
              <el-tag v-if="msg.model" size="small" type="success" effect="plain">
                {{ msg.model.provider }}
              </el-tag>
              <span class="message-time">{{ formatDateTime(new Date(msg.createdAt).toISOString()) }}</span>
            </div>

            <template v-if="msg.role === 'user'">
              <div class="user-bubble">{{ msg.content }}</div>
            </template>

            <template v-else>
              <div v-if="msg.sql" class="sql-panel">
                <div class="sql-head" @click="toggleSql(msg.id)">
                  <span>SQL 预览（只读）</span>
                  <el-icon>
                    <ArrowUp v-if="sqlOpen[msg.id]" />
                    <ArrowDown v-else />
                  </el-icon>
                </div>
                <pre v-show="sqlOpen[msg.id]" class="sql-code">{{ msg.sql }}</pre>
              </div>

              <div
                v-if="msg.content"
                class="answer markdown-body"
                v-html="renderMarkdown(msg.content)"
              ></div>
              <div v-else-if="msg.status === 'streaming'" class="answer streaming-hint">
                正在生成回答<span class="dots">...</span>
              </div>

              <div v-if="msg.result" class="result-block">
                <div class="block-title">
                  <el-icon><Grid /></el-icon>
                  查询结果
                </div>
                <ResultTable
                  :columns="msg.result.columns"
                  :rows="msg.result.rows"
                  :row-count="msg.result.row_count"
                  :max-height="260"
                />
              </div>

              <div v-if="msg.report" class="report-block">
                <div class="report-head">
                  <span class="report-title">{{ msg.report.title }}</span>
                  <el-button
                    v-if="msg.report.report_id"
                    link
                    type="primary"
                    size="small"
                    @click="openReport(msg.report.report_id)"
                  >
                    查看报表详情
                  </el-button>
                </div>
                <EChart
                  v-if="msg.report.option && msg.report.chart_type !== 'none'"
                  :option="msg.report.option"
                  height="300px"
                />
                <ResultTable
                  v-else
                  :columns="msg.report.columns"
                  :rows="msg.report.rows"
                  :row-count="msg.report.row_count"
                  :max-height="260"
                />
              </div>

              <CitationList
                v-if="msg.citations.length"
                :citations="msg.citations"
                @open-document="openDocument"
                @open-report="openReport"
              />

              <div v-if="msg.review" class="review-line">
                <el-tag
                  :type="msg.review.passed ? 'success' : 'warning'"
                  size="small"
                  effect="plain"
                >
                  {{ msg.review.passed ? '质量检查通过' : '质量检查提示' }}
                </el-tag>
                <span v-for="issue in msg.review.issues" :key="issue" class="review-issue">
                  {{ issue }}
                </span>
              </div>

              <div v-if="msg.error" class="error-line">
                <el-icon><CircleCloseFilled /></el-icon>
                <span>{{ msg.error }}</span>
              </div>
              <div v-if="msg.status === 'stopped'" class="muted stopped-line">已停止生成</div>

              <!-- 重试 / 重新生成按钮：只在本轮已结束且上一条是 user 时显示 -->
              <div
                v-if="!streaming && (msg.status === 'done' || msg.status === 'error' || msg.status === 'stopped')"
                class="retry-line"
              >
                <el-button
                  size="small"
                  link
                  type="primary"
                  :icon="Refresh"
                  @click="retryFromMessage(msg)"
                >
                  重新生成
                </el-button>
              </div>
            </template>
          </div>
        </div>
      </div>

      <footer class="chat-input">
        <el-input
          v-model="input"
          type="textarea"
          :autosize="{ minRows: 2, maxRows: 5 }"
          resize="none"
          placeholder="输入问题，例如：高值耗材的验收流程是什么？"
          :disabled="streaming"
          @keydown.enter.exact.prevent="send"
        />
        <div class="input-actions">
          <span class="muted input-tip">Enter 发送 / Shift + Enter 换行</span>
          <div class="input-buttons">
            <el-button v-if="streaming" type="danger" plain :icon="CircleClose" @click="stop">
              停止
            </el-button>
            <el-button
              v-else
              type="primary"
              :icon="Promotion"
              :disabled="!input.trim()"
              @click="send"
            >
              发送
            </el-button>
          </div>
        </div>
      </footer>
    </div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  ArrowDown,
  ArrowUp,
  ChatDotRound,
  CircleClose,
  CircleCloseFilled,
  Clock,
  Grid,
  Plus,
  Promotion,
  Refresh,
  Search
} from '@element-plus/icons-vue'

import CitationList from '@/components/CitationList.vue'
import EChart from '@/components/EChart.vue'
import ResultTable from '@/components/ResultTable.vue'
import { fetchSessionMessages, listSessions, streamChat } from '@/api/chat'
import type { ChatSessionItem } from '@/api/chat'
import { formatDateTime, intentLabel } from '@/utils/format'
import { renderMarkdown } from '@/utils/markdown'
import type {
  ChatMessage,
  Citation,
  ModelInfo,
  ReportPayload,
  ReviewPayload,
  SqlResult
} from '@/types/api'

const router = useRouter()

const suggestions = [
  '高值耗材的验收流程是什么？',
  '查询各科室消耗金额排名',
  '生成供应商履约率报表',
  '库存周转情况如何？'
]

const messages = ref<ChatMessage[]>([])
const input = ref('')
const streaming = ref(false)
const scrollRef = ref<HTMLDivElement>()
const sqlOpen = reactive<Record<string, boolean>>({})
const lastModel = ref<ModelInfo | null>(null)

// 历史对话
const historyVisible = ref(true)
const sessions = ref<ChatSessionItem[]>([])
const sessionKeyword = ref('')
const dateRange = ref<[string, string] | null>(null)
const sessionsLoading = ref(false)
const sessionsError = ref('')
const activeSessionId = ref<string | null>(null)
const historyLoading = ref(false)

let sessionId = createSessionId()
let controller: AbortController | null = null
let scrollScheduled = false

function createSessionId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID()
  }
  return `session-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function createMessage(role: 'user' | 'assistant', content = ''): ChatMessage {
  return {
    id: `${role}-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    role,
    content,
    status: role === 'user' ? 'done' : 'streaming',
    createdAt: Date.now(),
    citations: []
  }
}

function safeParse<T>(data: string): T | null {
  try {
    return JSON.parse(data) as T
  } catch {
    return null
  }
}

// ---------------------------------------------------------------------------
// 历史对话：列表查询 + 切换加载
// ---------------------------------------------------------------------------

async function loadSessions(): Promise<void> {
  sessionsLoading.value = true
  sessionsError.value = ''
  try {
    const [startDate, endDate] = dateRange.value || ['', '']
    sessions.value = await listSessions({
      keyword: sessionKeyword.value.trim() || undefined,
      start: startDate ? `${startDate}T00:00:00` : undefined,
      end: endDate ? `${endDate}T23:59:59` : undefined
    })
  } catch (error) {
    sessionsError.value = error instanceof Error ? error.message : '历史对话加载失败'
  } finally {
    sessionsLoading.value = false
  }
}

async function selectSession(item: ChatSessionItem): Promise<void> {
  if (streaming.value) {
    ElMessage.warning('请先停止当前回答再切换会话')
    return
  }
  if (item.session_id === activeSessionId.value) return

  activeSessionId.value = item.session_id
  sessionId = item.session_id
  lastModel.value = null
  historyLoading.value = true
  try {
    const list = await fetchSessionMessages(item.session_id)
    messages.value = list.map((m) => ({
      id: `history-${m.id}`,
      role: m.role,
      content: m.content,
      status: 'done' as const,
      createdAt: m.created_at ? new Date(m.created_at).getTime() : Date.now(),
      citations: m.citations || []
    }))
    scrollToBottom()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '历史消息加载失败')
  } finally {
    historyLoading.value = false
  }
}

async function send(): Promise<void> {
  const question = input.value.trim()
  if (!question || streaming.value) return

  messages.value.push(createMessage('user', question))
  const assistant = createMessage('assistant')
  messages.value.push(assistant)
  input.value = ''
  streaming.value = true
  scrollToBottom()

  controller = new AbortController()
  try {
    await streamChat(question, sessionId, (event, data) => handleEvent(assistant, event, data), controller.signal)
    if (assistant.status === 'streaming') {
      assistant.status = 'done'
    }
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      assistant.status = 'stopped'
    } else {
      assistant.status = 'error'
      assistant.error = error instanceof Error ? error.message : '对话请求失败'
    }
  } finally {
    streaming.value = false
    controller = null
    scrollToBottom()
    // 本轮结束后刷新历史列表，并把当前会话置为高亮
    activeSessionId.value = sessionId
    void loadSessions()
  }
}

function retryFromMessage(assistantMsg: ChatMessage): void {
  // 重新生成：找到这条 assistant 上一条 user 消息，清空 assistant 后重发请求
  if (streaming.value) return
  if (assistantMsg.role !== 'assistant') return

  const idx = messages.value.findIndex((m) => m.id === assistantMsg.id)
  if (idx < 1) return
  const prev = messages.value[idx - 1]
  if (prev.role !== 'user') return

  const question = prev.content
  // 清空 assistant 这条（保留 id 以便 UI 渲染同一位置）
  assistantMsg.content = ''
  assistantMsg.intent = undefined
  assistantMsg.sql = undefined
  assistantMsg.result = undefined
  assistantMsg.report = undefined
  assistantMsg.citations = []
  assistantMsg.review = undefined
  assistantMsg.model = undefined
  assistantMsg.error = undefined
  assistantMsg.status = 'streaming'

  controller = new AbortController()
  streaming.value = true
  scrollToBottom()
  streamChat(question, sessionId, (event, data) => handleEvent(assistantMsg, event, data), controller.signal)
    .then(() => {
      if (assistantMsg.status === 'streaming') assistantMsg.status = 'done'
    })
    .catch((err) => {
      if (err instanceof DOMException && err.name === 'AbortError') {
        assistantMsg.status = 'stopped'
      } else {
        assistantMsg.status = 'error'
        assistantMsg.error = err instanceof Error ? err.message : '重新生成失败'
      }
    })
    .finally(() => {
      streaming.value = false
      controller = null
      scrollToBottom()
    })
}

function handleEvent(msg: ChatMessage, event: string, data: string): void {
  switch (event) {
    case 'start':
      break
    case 'intent': {
      const payload = safeParse<{ intent?: string }>(data)
      if (payload?.intent) msg.intent = payload.intent
      break
    }
    case 'retrieval': {
      const payload = safeParse<{ count?: number }>(data)
      if (payload?.count !== undefined) msg.retrievalCount = payload.count
      break
    }
    case 'token':
      appendToken(msg, data)
      break
    case 'citations': {
      const payload = safeParse<Citation[]>(data)
      if (Array.isArray(payload)) msg.citations = payload
      break
    }
    case 'sql': {
      const payload = safeParse<{ sql?: string }>(data)
      if (payload?.sql) {
        msg.sql = payload.sql
        sqlOpen[msg.id] = true
      }
      break
    }
    case 'result': {
      const payload = safeParse<SqlResult>(data)
      if (payload && Array.isArray(payload.columns)) msg.result = payload
      break
    }
    case 'report': {
      const payload = safeParse<ReportPayload>(data)
      if (payload && Array.isArray(payload.columns)) {
        msg.report = payload
      }
      break
    }
    case 'review': {
      const payload = safeParse<ReviewPayload & { answer?: string }>(data)
      if (payload) {
        msg.review = {
          passed: payload.passed,
          level: payload.level,
          issues: payload.issues || [],
          model: payload.model
        }
        if (payload.answer) msg.content = payload.answer
        if (payload.model) {
          msg.model = payload.model
          lastModel.value = payload.model
        }
      }
      break
    }
    case 'model': {
      const payload = safeParse<ModelInfo>(data)
      if (payload) {
        msg.model = payload
        lastModel.value = payload
      }
      break
    }
    case 'error': {
      const payload = safeParse<{ message?: string }>(data)
      msg.error = payload?.message || data || 'AI 服务处理失败'
      msg.status = 'error'
      break
    }
    case 'done': {
      const payload = safeParse<{ model?: ModelInfo | null }>(data)
      if (payload?.model && !msg.model) {
        msg.model = payload.model
        lastModel.value = payload.model
      }
      if (msg.status === 'streaming') msg.status = 'done'
      break
    }
    default:
      break
  }
  scrollToBottom()
}

function appendToken(msg: ChatMessage, token: string): void {
  if (!token) return
  if (!msg.content) {
    msg.content = token
    return
  }
  // 后端按“累计全文”推送：新文本以已有内容开头时直接替换，否则按增量追加。
  if (token.startsWith(msg.content)) {
    msg.content = token
  } else if (!msg.content.endsWith(token)) {
    msg.content += token
  }
}

function stop(): void {
  controller?.abort()
}

function newSession(): void {
  if (streaming.value) {
    stop()
  }
  messages.value = []
  sessionId = createSessionId()
  activeSessionId.value = null
  lastModel.value = null
  ElMessage.success('已创建新会话')
}

onMounted(() => {
  void loadSessions()
})

function useSuggestion(question: string): void {
  input.value = question
}

function toggleSql(id: string): void {
  sqlOpen[id] = !sqlOpen[id]
}

function openDocument(docId: number, pageNo?: number): void {
  const query: Record<string, string> = { docId: String(docId) }
  if (pageNo) query.page = String(pageNo)
  router.push({ path: '/files', query })
}

function openReport(reportId: number): void {
  router.push({ path: '/reports', query: { reportId: String(reportId) } })
}

function scrollToBottom(): void {
  if (scrollScheduled) return
  scrollScheduled = true
  nextTick(() => {
    scrollScheduled = false
    const el = scrollRef.value
    if (el) el.scrollTop = el.scrollHeight
  })
}
</script>

<style scoped>
.chat-page {
  position: relative;
  display: flex;
  gap: 14px;
  height: 100%;
  padding: 16px;
}

/* ---------------- 历史对话侧栏 ---------------- */
.history-panel {
  flex: none;
  display: flex;
  flex-direction: column;
  gap: 10px;
  /* 随视口自适应，上下限保证窄屏不挤压、宽屏不过度拉伸 */
  width: clamp(216px, 22vw, 280px);
  min-width: 0;
  padding: 14px 12px;
  overflow: hidden;
}

.history-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.history-title-label {
  font-size: 14px;
  font-weight: 600;
  color: #334155;
}

/* 搜索框与日期选择器统一：撑满侧栏、禁止被 flex 压缩、高度一致 */
.history-search,
.history-date {
  flex: none;
  width: 100%;
  min-width: 0;
}

.history-search :deep(.el-input__wrapper) {
  height: 30px;
  box-sizing: border-box;
}

/* 日期范围选择器默认固定 350px 宽、内部输入框 39% 固定宽度，
   窄侧栏下会溢出并被裁切，这里统一改为撑满 + 可收缩 */
.history-panel :deep(.el-date-editor),
.history-panel :deep(.el-range-editor),
.history-date {
  width: 100% !important;
  min-width: 0 !important;
  max-width: 100% !important;
  box-sizing: border-box !important;
}

.history-panel :deep(.el-range-editor),
.history-date {
  height: 30px !important;
  min-height: 30px !important;
  max-height: 30px !important;
  padding: 0 8px;
  box-sizing: border-box !important;
}

/* 分隔符曾被拉伸到容器高度（282px），显式固定自身高度并居中 */
.history-panel :deep(.el-range-separator) {
  flex: 0 0 auto;
  align-self: center;
  display: inline-flex;
  align-items: center;
  height: 22px !important;
  padding: 0 2px;
  font-size: 11px;
  line-height: 1;
  white-space: nowrap;
}

.history-panel :deep(.el-range-input) {
  flex: 1 1 0;
  width: 0 !important;
  min-width: 0 !important;
  font-size: 12px;
  line-height: 1;
  text-align: center;
}

.history-panel :deep(.el-range__icon),
.history-panel :deep(.el-range__close-icon) {
  flex: 0 0 auto;
  margin: 0;
}

/* 弹层在窄屏下不超出视口 */
:global(.history-date-popper) {
  max-width: calc(100vw - 20px);
}

@media (max-width: 960px) {
  .history-panel {
    width: clamp(200px, 26vw, 240px);
    padding: 12px 10px;
  }

  .history-date :deep(.el-range-input) {
    font-size: 11px;
  }
}

@media (max-width: 820px) {
  .chat-page {
    padding: 8px;
  }

  /* 窄屏改为浮层，避免挤压聊天区 */
  .history-panel {
    position: absolute;
    inset: 8px auto 8px 8px;
    z-index: 20;
    width: min(280px, calc(100vw - 16px));
    background: #ffffff;
    box-shadow: 0 12px 32px rgba(15, 23, 42, 0.18);
  }
}

.history-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding-right: 2px;
}

.history-empty {
  padding: 24px 8px;
  text-align: center;
  font-size: 12px;
  color: var(--muted);
}

.history-error {
  color: #b91c1c;
}

.history-item {
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding: 9px 10px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: #f8fafc;
  text-align: left;
  cursor: pointer;
  transition: background 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease,
    transform 0.18s ease;
}

.history-item:hover {
  background: #eef4ff;
  border-color: #bfdbfe;
  transform: translateX(2px);
}

.history-item.active {
  background: #e8f0ff;
  border-color: var(--brand);
  box-shadow: inset 3px 0 0 var(--brand);
}

.history-item-title {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.history-item-preview {
  font-size: 12px;
  color: #64748b;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.history-item-meta {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: #94a3b8;
}

.chat-shell {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.chat-scroll {
  position: relative;
  transition: opacity 0.2s ease;
}

.chat-scroll.is-loading-history {
  opacity: 0.55;
}

.history-loading-mask {
  position: sticky;
  top: 0;
  z-index: 2;
  margin: 0 auto 10px;
  width: fit-content;
  padding: 4px 12px;
  border-radius: 999px;
  background: rgba(37, 99, 235, 0.9);
  color: #ffffff;
  font-size: 12px;
}

.chat-header {
  flex: none;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 20px 12px;
  border-bottom: 1px solid var(--border);
}

.chat-header h2 {
  margin: 0 0 4px;
  font-size: 18px;
}

.chat-header p {
  margin: 0;
}

.chat-header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.chat-scroll {
  flex: 1;
  min-height: 0;
  padding: 20px;
  overflow-y: auto;
  background: linear-gradient(180deg, #fbfcff, #f6f8fc);
}

.chat-welcome {
  max-width: 620px;
  margin: 40px auto;
  text-align: center;
}

.welcome-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 56px;
  height: 56px;
  margin-bottom: 14px;
  border-radius: 16px;
  background: #eef4ff;
  color: var(--brand);
  font-size: 26px;
}

.chat-welcome h3 {
  margin: 0 0 6px;
  font-size: 18px;
}

.suggestions {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 10px;
  margin-top: 18px;
}

.suggestion {
  padding: 8px 14px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: #ffffff;
  color: #334155;
  font-size: 13px;
  cursor: pointer;
  transition: border-color 0.15s ease, color 0.15s ease, box-shadow 0.15s ease;
}

.suggestion:hover {
  border-color: #93c5fd;
  color: var(--brand);
  box-shadow: 0 3px 10px rgba(37, 99, 235, 0.12);
}

.message {
  display: flex;
  gap: 10px;
  margin-bottom: 18px;
}

.message.user {
  flex-direction: row-reverse;
}

.avatar {
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 10px;
  background: #e2e8f0;
  color: #475569;
  font-size: 13px;
  font-weight: 600;
}

.message.user .avatar {
  background: var(--brand);
  color: #fff;
}

.message-body {
  max-width: min(860px, 88%);
}

.message.user .message-body {
  max-width: 72%;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}

.message-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 6px;
  font-size: 12px;
  color: var(--muted);
}

.sender {
  font-weight: 600;
  color: #475569;
}

.message-time {
  color: #94a3b8;
}

.user-bubble {
  padding: 10px 14px;
  border-radius: 10px 2px 10px 10px;
  background: var(--brand);
  color: #ffffff;
  font-size: 14px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}

.message.assistant .message-body {
  padding: 12px 16px;
  border: 1px solid var(--border);
  border-radius: 2px 10px 10px 10px;
  background: #ffffff;
}

.answer {
  margin-top: 2px;
}

.streaming-hint {
  color: var(--muted);
  font-size: 14px;
}

.dots {
  display: inline-block;
  animation: blink 1.2s infinite;
}

@keyframes blink {
  0%,
  100% {
    opacity: 0.2;
  }
  50% {
    opacity: 1;
  }
}

.sql-panel {
  margin: 8px 0 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
  background: #f8fafc;
}

.sql-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  font-size: 12px;
  font-weight: 600;
  color: #475569;
  cursor: pointer;
  user-select: none;
}

.sql-code {
  margin: 0;
  padding: 10px 12px;
  max-height: 180px;
  overflow: auto;
  border-top: 1px solid var(--border);
  background: #ffffff;
  font-family: Consolas, 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
  color: #334155;
}

.result-block,
.report-block {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed var(--border);
}

.block-title {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--muted);
}

.report-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.report-title {
  font-size: 14px;
  font-weight: 600;
}

.review-line {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px dashed var(--border);
  font-size: 12px;
}

.review-issue {
  color: #b45309;
}

.error-line {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  background: #fef2f2;
  color: #b91c1c;
  font-size: 13px;
}

.stopped-line {
  margin-top: 8px;
}

.retry-line {
  margin-top: 8px;
  padding-top: 6px;
  border-top: 1px dashed var(--border);
}

.chat-input {
  flex: none;
  padding: 12px 20px 14px;
  border-top: 1px solid var(--border);
  background: #ffffff;
}

.input-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 8px;
}

.input-tip {
  font-size: 12px;
}

@media (max-width: 720px) {
  .chat-page {
    padding: 8px;
  }

  .chat-header p {
    display: none;
  }

  .message-body,
  .message.user .message-body {
    max-width: 100%;
  }

  .input-tip {
    display: none;
  }
}
</style>
